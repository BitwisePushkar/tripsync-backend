import logging
from django.conf import settings
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
from account import tasks
import re as _re
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from account.models import UserSocialAccount

User = get_user_model()
logger = logging.getLogger("account")

def _get_tokens_for_user(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }

def _blacklist_all_user_tokens(user) -> None:
    outstanding = OutstandingToken.objects.filter(user=user)
    count = 0
    for token in outstanding:
        _, created = BlacklistedToken.objects.get_or_create(token=token)
        if created:
            count += 1
    logger.info("Blacklisted %d token(s) for user %s", count, user.email)


def _generate_username_from_name(name: str, email: str) -> str:
    base = _re.sub(r"[^a-z0-9_@#]", "", name.lower().replace(" ", ""))
    if not base or len(base) < 3:
        base = email.split("@")[0]
        base = _re.sub(r"[^a-z0-9_@#]", "", base.lower())
    base = base[:15]
    if len(base) < 5:
        base = base.ljust(5, "1")
    candidate = base
    counter = 1
    while User.objects.filter(username=candidate).exists():
        suffix = str(counter)
        candidate = base[: 15 - len(suffix)] + suffix
        counter += 1
    return candidate

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

_ERROR_401 = OpenApiResponse(
    response=OpenApiTypes.OBJECT,
    description="Authentication required",
    examples=[
        OpenApiExample(
            "Unauthorized",
            value={"status": "error", "message": "Authentication credentials were not provided."},
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
        summary="Register — step 1 (request OTP)",
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
        if User.objects.filter(email=email, is_email_verified=True).exists():
            return Response(
                {"status": "error", "message": "An account with this email already exists.",
                 "errors": {"email": ["This email is already registered."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(username=username).exists():
            return Response(
                {"status": "error", "message": "This username is already taken.",
                 "errors": {"username": ["This username is already taken."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        eligible, err_msg = otp_service.check_resend_eligibility(email)
        if not eligible:
            return Response(
                {"status": "error", "message": err_msg},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        otp_service.store_unverified_user(email, username, password)
        otp_code = otp_service.generate_and_store_otp(email, "registration")
        tasks.send_otp_email_task.delay(email, otp_code, "registration")
        logger.info("Registration initiated for %s", email)
        return Response(
            {
                "status": "success",
                "message": "OTP sent to your email. Please verify to complete registration.",
                "data": {"email": email, "otp_expires_in": f"{settings.OTP_EXPIRY_MINUTES} minutes"},
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
        summary="Register — step 2 (verify OTP)",
        description=("Verifies the 6-digit OTP. On success the account is created and JWT tokens returned."),
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
                {"status": "error", "message": "Registration session expired. Please register again."},
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
        tasks.send_welcome_email_task.delay(user.email, user.username)
        logger.info("New user registered: %s (@%s)", user.email, user.username)
        return Response(
            {
                "status": "success",
                "message": "Account created successfully!",
                "data": {
                    "user": {"id": user.id, "email": user.email, "username": user.username},
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
        tasks.send_otp_email_task.delay(email, otp_code, otp_type)
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
        description="Authenticate using email or username + password.\n\n**Rate limit:** 5 wrong attempts → 1 hour lock.",
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
                {"status": "error",
                 "message": f"Too many failed attempts. Try again in {minutes_remaining} minute(s)."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        try:
            user = (
                User.objects.get(email=identifier)
                if "@" in identifier
                else User.objects.get(username=identifier)
            )
        except User.DoesNotExist:
            otp_service.record_failed_login(identifier)
            return Response(
                {"status": "error", "message": "Invalid credentials.",
                 "errors": {"non_field_errors": ["Email/username or password is incorrect."]}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not user.check_password(password):
            now_locked, remaining = otp_service.record_failed_login(identifier)
            if now_locked:
                return Response(
                    {"status": "error",
                     "message": f"Too many failed attempts. Account locked for {settings.LOGIN_LOCK_DURATION_MINUTES} minute(s)."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            return Response(
                {"status": "error", "message": "Invalid credentials.",
                 "errors": {"non_field_errors": [f"Email/username or password is incorrect. {remaining} attempt(s) remaining."]}},
                status=status.HTTP_401_UNAUTHORIZED,
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
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active", "updated_at"])
            logger.info("Account reactivated on login: %s", user.email)
        otp_service.clear_login_lock(identifier)
        tokens = _get_tokens_for_user(user)
        logger.info("User logged in: %s", user.email)
        return Response(
            {
                "status": "success",
                "message": "Login successful.",
                "data": {
                    "user": {"id": user.id, "email": user.email, "username": user.username},
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
                "properties": {"refresh": {"type": "string", "example": "eyJ..."}},
            }
        },
        responses={
            200: OpenApiResponse(description="Logged out successfully"),
            400: _ERROR_400,
            401: _ERROR_401,
        },
        tags=["Authentication"],
        summary="Logout",
        description="Blacklists the refresh token. Requires `Authorization: Bearer <access_token>`.",
    )
    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"status": "error", "message": "Refresh token is required.",
                 "errors": {"refresh": ["This field is required."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response(
                {"status": "error", "message": "Invalid or expired refresh token.",
                 "errors": {"refresh": ["Token is invalid or already blacklisted."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        logger.info("User logged out: %s", request.user.email)
        return Response({"status": "success", "message": "Logged out successfully."}, status=status.HTTP_200_OK)

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
                        value={"status": "success",
                               "message": "If that email is registered, an OTP has been sent.",
                               "data": {"otp_expires_in": "10 minutes"}},
                    )
                ],
            ),
            429: _ERROR_429,
        },
        tags=["Authentication"],
        summary="Password reset — step 1 (request OTP)",
        description="Sends reset OTP to the email if registered and verified. Response is identical either way (anti-enumeration).",
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
                {"status": "error", "message": f"Account locked. Try again in {minutes_remaining} minute(s)."},
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
            tasks.send_otp_email_task.delay(user.email, otp_code, "password_reset")
            logger.info("Password reset OTP sent to %s", email)
        except User.DoesNotExist:
            logger.debug("Password reset requested for unknown/unverified email: %s", email)
        return Response(
            {"status": "success", "message": "If that email is registered, an OTP has been sent.",
             "data": {"otp_expires_in": f"{settings.OTP_EXPIRY_MINUTES} minutes"}},
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
                        value={"status": "success",
                               "message": "OTP verified. Use the reset token to set your new password.",
                               "data": {"reset_token": "abc123...", "expires_in": "5 minutes"}},
                    )
                ],
            ),
            400: _ERROR_400,
            429: _ERROR_429,
        },
        tags=["Authentication"],
        summary="Password reset — step 2 (verify OTP)",
        description="Verifies OTP. Returns a `reset_token` (5 min, one-time) for step 3.",
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
        success, message, attempts_remaining = otp_service.verify_otp(email, otp_code, "password_reset")
        if not success:
            resp_status = (
                status.HTTP_429_TOO_MANY_REQUESTS if attempts_remaining <= 0
                else status.HTTP_400_BAD_REQUEST
            )
            resp = {"status": "error", "message": message}
            if attempts_remaining > 0:
                resp["attempts_remaining"] = attempts_remaining
            return Response(resp, status=resp_status)
        reset_token = otp_service.store_reset_token(email)
        return Response(
            {"status": "success",
             "message": "OTP verified. Use the reset token to set your new password.",
             "data": {"reset_token": reset_token, "expires_in": f"{settings.RESET_TOKEN_EXPIRY_MINUTES} minutes"}},
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
                        value={"status": "success",
                               "message": "Password reset successfully. Please log in with your new password."},
                    )
                ],
            ),
            400: _ERROR_400,
        },
        tags=["Authentication"],
        summary="Password reset — step 3 (set new password)",
        description="Sets new password using the `reset_token` from step 2. All existing sessions invalidated.",
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
        if not otp_service.verify_and_consume_reset_token(email, reset_token):
            return Response(
                {"status": "error",
                 "message": "Invalid or expired reset token. Please restart the password reset process.",
                 "errors": {"reset_token": ["Token is invalid or expired."]}},
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
            {"status": "success", "message": "Password reset successfully. Please log in with your new password."},
            status=status.HTTP_200_OK,
        )

class DeactivateAccountView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        request=serializers.ConfirmPasswordSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Account deactivated",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={"status": "success", "message": "Your account has been deactivated."},
                    )
                ],
            ),
            400: _ERROR_400,
            401: _ERROR_401,
        },
        tags=["Authentication"],
        summary="Deactivate account (soft delete)",
        description=("Sets the account as inactive. You will be logged out on all devices."),
    )
    def post(self, request):
        serializer = serializers.ConfirmPasswordSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        password = serializer.validated_data["password"]
        user = request.user
        if not user.check_password(password):
            return Response(
                {"status": "error", "message": "Incorrect password.",
                 "errors": {"password": ["Password is incorrect."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _blacklist_all_user_tokens(user)
        user.is_active = False
        user.save()
        logger.info("Account deactivated: %s", user.email)
        return Response(
            {"status": "success", "message": "Your account has been deactivated."},
            status=status.HTTP_200_OK,
        )

class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        request=serializers.ConfirmPasswordSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Account permanently deleted",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={"status": "success",
                               "message": "Your account has been permanently deleted."},
                    )
                ],
            ),
            400: _ERROR_400,
            401: _ERROR_401,
        },
        tags=["Authentication"],
        summary="Delete account (permanent)",
        description=("**Permanently** deletes the account. This cannot be undone."),
    )
    def delete(self, request):
        serializer = serializers.ConfirmPasswordSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        password = serializer.validated_data["password"]
        user = request.user
        if not user.check_password(password):
            return Response(
                {"status": "error", "message": "Incorrect password.",
                 "errors": {"password": ["Password is incorrect."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        email = user.email
        username = user.username
        _blacklist_all_user_tokens(user)
        tasks.send_goodbye_email_task.delay(email, username)
        user.delete()
        logger.info("Account permanently deleted: %s (@%s)", email, username)
        return Response(
            {"status": "success", "message": "Your account has been permanently deleted."},
            status=status.HTTP_200_OK,
        )
    
class GoogleAuthView(APIView):
    @extend_schema(
        request=serializers.GoogleAuthSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Authenticated — JWT tokens returned",
                examples=[
                    OpenApiExample(
                        "Existing user",
                        value={
                            "status": "success",
                            "message": "Login successful.",
                            "data": {
                                "is_new_user": False,
                                "user": {
                                    "id": 1,
                                    "email": "user@gmail.com",
                                    "username": "johndoe",
                                },
                                "tokens": {
                                    "access": "eyJ...",
                                    "refresh": "eyJ...",
                                },
                            },
                        },
                    ),
                    OpenApiExample(
                        "New user registered via Google",
                        value={
                            "status": "success",
                            "message": "Account created via Google.",
                            "data": {
                                "is_new_user": True,
                                "user": {
                                    "id": 2,
                                    "email": "newuser@gmail.com",
                                    "username": "janedoe",
                                },
                                "tokens": {
                                    "access": "eyJ...",
                                    "refresh": "eyJ...",
                                },
                            },
                        },
                    ),
                ],
            ),
            400: _ERROR_400,
            401: OpenApiResponse(description="Invalid or expired Google ID token"),
            409: OpenApiResponse(description="Google account already linked to another TripSync account"),
        },
        tags=["Authentication"],
        summary="Google Sign-In",
        description="Google ID token login (Kotlin). Returns JWT + `is_new_user`.",
    )
    def post(self, request):
        serializer = serializers.GoogleAuthSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        raw_token = serializer.validated_data["id_token"]
        client_ids = settings.GOOGLE_OAUTH_CLIENT_IDS
        if not client_ids:
            logger.error("GOOGLE_OAUTH_CLIENT_IDS not configured in settings")
            return Response({"status": "error", "message": "Google authentication is not configured on this server.",},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,)
        google_info = None
        last_error = None
        for client_id in client_ids:
            try:
                google_info = google_id_token.verify_oauth2_token(raw_token, google_requests.Request(),
                                                                   audience=client_id,)
                break
            except ValueError as e:
                last_error = str(e)
                continue 
        if google_info is None:
            logger.warning("Google token verification failed: %s", last_error)
            return Response(
                {
                    "status": "error",
                    "message": "Invalid or expired Google token. Please sign in again.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
        google_uid = google_info.get("sub")
        email = google_info.get("email", "").lower().strip()
        name = google_info.get("name", "")
        if not email:
            return Response(
                {
                    "status": "error",
                    "message": "Email permission is required. Please grant email access in Google Sign-In.",
                    "errors": {"email": ["Email not provided by Google."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not google_uid:
            logger.error("Google token missing 'sub' claim — token: truncated for security")
            return Response(
                {
                    "status": "error",
                    "message": "Could not extract user identity from Google token.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        is_new_user = False
        try:
            social = UserSocialAccount.objects.select_related("user").get(
                provider=UserSocialAccount.PROVIDER_GOOGLE,
                provider_uid=google_uid,
            )
            user = social.user
            if not User.objects.filter(pk=user.pk).exists():
                social.delete()
                raise UserSocialAccount.DoesNotExist
        except UserSocialAccount.DoesNotExist:
            try:
                user = User.objects.get(email=email)
                if UserSocialAccount.objects.filter(
                    provider=UserSocialAccount.PROVIDER_GOOGLE,
                    provider_uid=google_uid,
                ).exclude(user=user).exists():
                    return Response(
                        {
                            "status": "error",
                            "message": "This Google account is already linked to a different TripSync account.",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                UserSocialAccount.objects.create(
                    user=user,
                    provider=UserSocialAccount.PROVIDER_GOOGLE,
                    provider_uid=google_uid,
                )
                logger.info(
                    "Google account linked to existing user: %s (uid=%s)",
                    email, google_uid,
                )
            except User.DoesNotExist:
                username  = _generate_username_from_name(name, email)
                user = User.objects.create_user(
                    email=email,
                    username=username,
                    password=None,
                )
                user.is_email_verified = True
                user.save(update_fields=["is_email_verified"])
                UserSocialAccount.objects.create(
                    user=user,
                    provider=UserSocialAccount.PROVIDER_GOOGLE,
                    provider_uid=google_uid,
                )
                tasks.send_welcome_email_task.delay(user.email, user.username)
                is_new_user = True
                logger.info(
                    "New user created via Google Sign-In: %s (@%s)",
                    email, username,
                )
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active", "updated_at"])
            logger.info("Account reactivated via Google Sign-In: %s", email)
        tokens = _get_tokens_for_user(user)
        logger.info("Google Sign-In successful: %s (new=%s)", email, is_new_user)
        return Response(
            {
                "status": "success",
                "message": "Account created via Google." if is_new_user else "Login successful.",
                "data": {
                    "is_new_user": is_new_user,
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