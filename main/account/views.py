import logging
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample, OpenApiTypes
from account import otp_service
from account import serializers
from django.conf import settings
from account.tasks import send_otp_email_task, send_welcome_email_task

User = get_user_model()
logger = logging.getLogger("account")

def _get_tokens_for_user(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }

_ERROR_400 = OpenApiResponse(
    response=OpenApiTypes.OBJECT,
    description="Validation error or bad request",
    examples=[
        OpenApiExample(
            "Validation Error",
            value={"status": "error", "message": "...", "errors": {"field": ["detail"]}},
        )
    ],
)

_ERROR_429 = OpenApiResponse(
    response=OpenApiTypes.OBJECT,
    description="Rate limit exceeded or account locked",
    examples=[
        OpenApiExample(
            "Rate Limited",
            value={"status": "error", "message": "Account locked. Try again in 60 minute(s)."},
        )
    ],
)

class UserRegistrationView(APIView):
    @extend_schema(
        request=serializers.UserRegistrationSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="OTP sent — awaiting email verification",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={
                            "status": "success",
                            "message": "OTP sent to your email. Please verify to complete registration.",
                            "data": {"email": "user@example.com", "otp_expires_in": "10 minutes"},
                        },
                    )
                ],
            ),
            400: _ERROR_400,
            429: _ERROR_429,
        },
        tags=["Authentication"],
        summary="Register a new user — step 1 (request OTP)",
        description=("Call `/api/account/verify-otp/` next."),
    )
    def post(self, request):
        serializer = serializers.UserRegistrationSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        email = serializer.validated_data["email"]
        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]
        eligible, err_msg = otp_service.check_resend_eligibility(email)
        if not eligible:
            return Response(
                {"status": "error", "message": err_msg},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        otp_service.store_unverified_user(email, username, password)
        otp_code = otp_service.generate_and_store_otp(email, "registration")
        send_otp_email_task.delay(email, otp_code, "registration")
        logger.info("Registration initiated for %s", email)
        return Response(
            {
                "status": "success",
                "message": "OTP sent to your email. Please verify to complete registration.",
                "data": {
                    "email": email,
                    "otp_expires_in": f"{settings.OTP_EXPIRY_MINUTES} minutes",
                },
            },
            status=status.HTTP_200_OK,
        )

class VerifyRegistrationOTPView(APIView):
    @extend_schema(
        request=serializers.VerifyOTPSerializer,
        responses={
            201: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Account created — JWT tokens returned",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={
                            "status": "success",
                            "message": "Account created successfully!",
                            "data": {
                                "user": {"id": 1, "email": "user@example.com", "username": "travelr"},
                                "tokens": {"access": "eyJ...", "refresh": "eyJ..."},
                            },
                        },
                    )
                ],
            ),
            400: _ERROR_400,
            409: OpenApiResponse(description="Email or username taken (race condition)"),
            429: _ERROR_429,
        },
        tags=["Authentication"],
        summary="Verify registration OTP — step 2 (complete registration)",
        description=("Verifies the 6-digit OTP and JWT tokens are returned."),
    )
    def post(self, request):
        serializer = serializers.VerifyOTPSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        email = serializer.validated_data["email"]
        otp_code = serializer.validated_data["otp"]
        success, message, attempts_remaining = otp_service.verify_otp(
            email, otp_code, "registration"
        )
        if not success:
            resp_status = (
                status.HTTP_429_TOO_MANY_REQUESTS
                if attempts_remaining <= 0
                else status.HTTP_400_BAD_REQUEST
            )
            resp = {"status": "error", "message": message}
            if attempts_remaining > 0:
                resp["attempts_remaining"] = attempts_remaining
            return Response(resp, status=resp_status)
        pending = otp_service.get_unverified_user(email)
        if not pending:
            return Response(
                {
                    "status": "error",
                    "message": "Registration session expired. Please register again.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(email=pending["email"], is_email_verified=True).exists():
            otp_service.clear_all_otp_keys(email)
            return Response(
                {"status": "error", "message": "This email is already registered."},
                status=status.HTTP_409_CONFLICT,
            )
        if User.objects.filter(username=pending["username"]).exists():
            otp_service.clear_all_otp_keys(email)
            return Response(
                {"status": "error", "message": "This username is already taken."},
                status=status.HTTP_409_CONFLICT,
            )
        user = User.objects.create_user(
            email=pending["email"],
            username=pending["username"],
            password=pending["password"], 
        )
        user.is_email_verified = True
        user.save()
        otp_service.clear_all_otp_keys(email)
        tokens = _get_tokens_for_user(user)
        send_welcome_email_task.delay(user.email, user.username)
        logger.info("New user registered: %s (@%s)", user.email, user.username)
        return Response(
            {
                "status": "success",
                "message": "Account created successfully!",
                "data": {
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "username": user.username,
                    },
                    "tokens": tokens,
                },
            },
            status=status.HTTP_201_CREATED,
        )

class ResendOTPView(APIView):
    @extend_schema(
        request=serializers.ResendOTPSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="OTP resent successfully",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={
                            "status": "success",
                            "message": "OTP resent to your email.",
                            "data": {"email": "user@example.com", "otp_type": "registration"},
                        },
                    )
                ],
            ),
            400: _ERROR_400,
            429: _ERROR_429,
        },
        tags=["Authentication"],
        summary="Resend OTP",
        description=("Resends the OTP for registration or password reset."),
    )
    def post(self, request):
        serializer = serializers.ResendOTPSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        email = serializer.validated_data["email"]
        pending = otp_service.get_unverified_user(email)
        if pending:
            otp_type = "registration"
        else:
            user_exists = User.objects.filter(
                email=email, is_email_verified=True
            ).exists()
            if not user_exists:
                return Response(
                    {"status": "error", "message": "No active OTP session found for this email."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            otp_type = "password_reset"
        eligible, err_msg = otp_service.check_resend_eligibility(email)
        if not eligible:
            return Response(
                {"status": "error", "message": err_msg},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        otp_code = otp_service.generate_and_store_otp(email, otp_type)
        send_otp_email_task.delay(email, otp_code, otp_type)
        logger.info("OTP resent for %s (type=%s)", email, otp_type)
        return Response(
            {
                "status": "success",
                "message": "OTP resent to your email.",
                "data": {"email": email, "otp_type": otp_type},
            },
            status=status.HTTP_200_OK,
        )

class UserLoginView(APIView):
    @extend_schema(
        request=serializers.UserLoginSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Login successful",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={
                            "status": "success",
                            "message": "Login successful.",
                            "data": {
                                "user": {"id": 1, "email": "user@example.com", "username": "travelr"},
                                "tokens": {"access": "eyJ...", "refresh": "eyJ..."},
                            },
                        },
                    )
                ],
            ),
            401: OpenApiResponse(description="Invalid credentials"),
            403: OpenApiResponse(description="Account not verified or deactivated"),
            429: _ERROR_429,
        },
        tags=["Authentication"],
        summary="Login (email or username)",
        description=("Authenticate using either email address or username plus password."),
    )
    def post(self, request):
        serializer = serializers.UserLoginSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        identifier = serializer.validated_data["identifier"]
        password = serializer.validated_data["password"]
        is_locked, minutes_remaining = otp_service.check_login_lock(identifier)
        if is_locked:
            return Response(
                {
                    "status": "error",
                    "message": f"Too many failed attempts. Try again in {minutes_remaining} minute(s).",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        try:
            if "@" in identifier:
                user = User.objects.get(email=identifier)
            else:
                user = User.objects.get(username=identifier)
        except User.DoesNotExist:
            otp_service.record_failed_login(identifier)
            return Response(
                {
                    "status": "error",
                    "message": "Invalid credentials.",
                    "errors": {"non_field_errors": ["Email/username or password is incorrect."]},
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not user.check_password(password):
            now_locked, remaining = otp_service.record_failed_login(identifier)
            if now_locked:
                return Response(
                    {
                        "status": "error",
                        "message": f"Too many failed attempts. Account locked for "
                                   f"{settings.LOGIN_LOCK_DURATION_MINUTES} minute(s).",
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            return Response(
                {
                    "status": "error",
                    "message": "Invalid credentials.",
                    "errors": {
                        "non_field_errors": [
                            f"Email/username or password is incorrect. "
                            f"{remaining} attempt(s) remaining."
                        ]
                    },
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not user.is_active:
            return Response(
                {
                    "status": "error",
                    "message": "This account has been deactivated. Contact support.",
                    "errors": {"account": ["Account deactivated"]},
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if not user.is_email_verified:
            return Response(
                {
                    "status": "error",
                    "message": "Email not verified. Please complete registration first.",
                    "errors": {"account": ["Email not verified"]},
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        otp_service.clear_login_lock(identifier)
        tokens = _get_tokens_for_user(user)
        logger.info("User logged in: %s", user.email)
        return Response(
            {
                "status": "success",
                "message": "Login successful.",
                "data": {
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "username": user.username,
                    },
                    "tokens": tokens,
                },
            },
            status=status.HTTP_200_OK,
        )

class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "required": ["refresh"],
                "properties": {
                    "refresh": {"type": "string", "example": "eyJ..."}
                },
            }
        },
        responses={
            200: OpenApiResponse(description="Logged out successfully"),
            400: _ERROR_400,
            401: OpenApiResponse(description="Missing or invalid Authorization header"),
        },
        tags=["Authentication"],
        summary="Logout",
        description=("Blacklists the refresh token. The access token expires naturally."),
    )
    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {
                    "status": "error",
                    "message": "Refresh token is required.",
                    "errors": {"refresh": ["This field is required."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response(
                {
                    "status": "error",
                    "message": "Invalid or expired refresh token.",
                    "errors": {"refresh": ["Token is invalid or already blacklisted."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        logger.info("User logged out: %s", request.user.email)
        return Response(
            {"status": "success", "message": "Logged out successfully."},
            status=status.HTTP_200_OK,
        )

class PasswordResetRequestView(APIView):
    @extend_schema(
        request=serializers.PasswordResetRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="OTP sent (or silently skipped for unknown email)",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={
                            "status": "success",
                            "message": "If that email is registered, an OTP has been sent.",
                            "data": {"otp_expires_in": "10 minutes"},
                        },
                    )
                ],
            ),
            429: _ERROR_429,
        },
        tags=["Authentication"],
        summary="Request password reset OTP — step 1",
        description=("Follow up with `/api/account/password/reset/verify-otp/`."),
    )
    def post(self, request):
        serializer = serializers.PasswordResetRequestSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        email = serializer.validated_data["email"]
        is_locked, minutes_remaining = otp_service.check_login_lock(email)
        if is_locked:
            return Response(
                {
                    "status": "error",
                    "message": f"Account locked. Try again in {minutes_remaining} minute(s).",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        eligible, err_msg = otp_service.check_resend_eligibility(email)
        if not eligible:
            return Response(
                {"status": "error", "message": err_msg},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        try:
            user = User.objects.get(email=email, is_email_verified=True)
            otp_code = otp_service.generate_and_store_otp(email, "password_reset")
            send_otp_email_task.delay(user.email, otp_code, "password_reset")
            logger.info("Password reset OTP sent to %s", email)
        except User.DoesNotExist:
            logger.debug("Password reset requested for unknown/unverified email: %s", email)
        return Response(
            {
                "status": "success",
                "message": "If that email is registered, an OTP has been sent.",
                "data": {"otp_expires_in": f"{settings.OTP_EXPIRY_MINUTES} minutes"},
            },
            status=status.HTTP_200_OK,
        )

class PasswordResetVerifyOTPView(APIView):
    @extend_schema(
        request=serializers.PasswordResetVerifyOTPSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="OTP verified — reset token returned",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={
                            "status": "success",
                            "message": "OTP verified. Use the reset token to set your new password.",
                            "data": {
                                "reset_token": "abc123...",
                                "expires_in": "5 minutes",
                            },
                        },
                    )
                ],
            ),
            400: _ERROR_400,
            429: _ERROR_429,
        },
        tags=["Authentication"],
        summary="Verify password reset OTP — step 2",
        description=("Submit it to `/api/account/password/reset/confirm/` to set a new password."),
    )
    def post(self, request):
        serializer = serializers.PasswordResetVerifyOTPSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        email = serializer.validated_data["email"]
        otp_code = serializer.validated_data["otp"]
        if not User.objects.filter(email=email, is_email_verified=True).exists():
            return Response(
                {"status": "error", "message": "No account found for this email."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        success, message, attempts_remaining = otp_service.verify_otp(
            email, otp_code, "password_reset"
        )
        if not success:
            resp_status = (
                status.HTTP_429_TOO_MANY_REQUESTS
                if attempts_remaining <= 0
                else status.HTTP_400_BAD_REQUEST
            )
            resp = {"status": "error", "message": message}
            if attempts_remaining > 0:
                resp["attempts_remaining"] = attempts_remaining
            return Response(resp, status=resp_status)
        reset_token = otp_service.store_reset_token(email)
        return Response(
            {
                "status": "success",
                "message": "OTP verified. Use the reset token to set your new password.",
                "data": {
                    "reset_token": reset_token,
                    "expires_in": f"{settings.RESET_TOKEN_EXPIRY_MINUTES} minutes",
                },
            },
            status=status.HTTP_200_OK,
        )

class PasswordResetConfirmView(APIView):
    @extend_schema(
        request=serializers.PasswordResetConfirmSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Password reset successfully",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={
                            "status": "success",
                            "message": "Password reset successfully. Please log in with your new password.",
                        },
                    )
                ],
            ),
            400: _ERROR_400,
        },
        tags=["Authentication"],
        summary="Confirm password reset — step 3 (set new password)",
        description=("The user must log in again on all devices."),
    )
    def post(self, request):
        serializer = serializers.PasswordResetConfirmSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        email = serializer.validated_data["email"]
        reset_token = serializer.validated_data["reset_token"]
        new_password = serializer.validated_data["new_password"]
        token_valid = otp_service.verify_and_consume_reset_token(email, reset_token)
        if not token_valid:
            return Response(
                {
                    "status": "error",
                    "message": "Invalid or expired reset token. Please restart the password reset process.",
                    "errors": {"reset_token": ["Token is invalid or expired."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            user = User.objects.get(email=email, is_email_verified=True)
        except User.DoesNotExist:
            return Response(
                {"status": "error", "message": "User not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(new_password)
        user.save()
        _blacklist_all_user_tokens(user)
        logger.info("Password reset completed for %s", email)
        return Response(
            {
                "status": "success",
                "message": "Password reset successfully. Please log in with your new password.",
            },
            status=status.HTTP_200_OK,
        )

def _blacklist_all_user_tokens(user) -> None:
    outstanding = OutstandingToken.objects.filter(user=user)
    count = 0
    for token in outstanding:
        _, created = BlacklistedToken.objects.get_or_create(token=token)
        if created:
            count += 1
    logger.info(
        "Blacklisted %d token(s) for user %s after password reset",
        count,
        user.email,
    )