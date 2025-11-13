import re
import secrets
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
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from account import otp_service
from account import serializers
from account import tasks

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

def _generate_username_from_email(email: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_@#]", "", email.split("@")[0])[:12].lower()
    if len(base) < 5:
        base = base + "user"
    candidate = base
    while User.objects.filter(username=candidate).exists():
        candidate = (base[:10] + secrets.token_hex(2)).lower()
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
                {"status": "error", "message": "An account with this email already exists.",
                 "errors": {"email": ["This email is already registered."]}},
                status=status.HTTP_409_CONFLICT,
            )
        if User.objects.filter(username=pending["username"]).exists():
            otp_service.clear_all_otp_keys(email)
            return Response(
                {"status": "error", "message": "This username is already taken.",
                 "errors": {"username": ["This username is already taken."]}},
                status=status.HTTP_409_CONFLICT,
            )
        user = User.objects.create_user(
            email=pending["email"],
            username=pending["username"],
            password=pending["password"],
        )
        user.is_email_verified = True
        user.save()
        otp_service.delete_unverified_user(email)
        tokens = _get_tokens_for_user(user)
        logger.info("Account created for %s (@%s)", user.email, user.username)
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
                description="OTP resent",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={"status": "success", "message": "A new OTP has been sent to your email.",
                               "data": {"email": "user@example.com", "otp_expires_in": "10 minutes"}},
                    )
                ],
            ),
            400: _ERROR_400,
            429: _ERROR_429,
        },
        tags=["Authentication"],
        summary="Register — resend OTP",
        description="Resends a fresh OTP for registration. Subject to cooldown and resend limits.",
    )
    def post(self, request):
        serializer = serializers.ResendOTPSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        email = serializer.validated_data["email"]
        pending = otp_service.get_unverified_user(email)
        if not pending:
            return Response(
                {"status": "error", "message": "No pending registration found. Please register again.",
                 "errors": {"email": ["No pending registration for this email."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        eligible, err_msg = otp_service.check_resend_eligibility(email)
        if not eligible:
            return Response(
                {"status": "error", "message": err_msg},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        otp_code = otp_service.generate_and_store_otp(email, "registration")
        tasks.send_otp_email_task.delay(email, otp_code, "registration")
        logger.info("OTP resent for %s", email)
        return Response(
            {"status": "success", "message": "A new OTP has been sent to your email.",
             "data": {"email": email, "otp_expires_in": f"{settings.OTP_EXPIRY_MINUTES} minutes"}},
            status=status.HTTP_200_OK,
        )

class UserLoginView(APIView):
    @extend_schema(
        request=serializers.UserLoginSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Login successful — JWT tokens returned",
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
            400: _ERROR_400,
            429: _ERROR_429,
        },
        tags=["Authentication"],
        summary="Login",
        description="Authenticate with email or username + password. Returns JWT tokens.",
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
                 "message": f"Account locked due to too many failed attempts. Try again in {minutes_remaining} minute(s)."},
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
                {"status": "error", "message": "Invalid credentials.",
                 "errors": {"identifier": ["No account found with these credentials."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.is_email_verified:
            return Response(
                {"status": "error", "message": "Email not verified. Please complete registration.",
                 "errors": {"identifier": ["Email address is not verified."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.is_active:
            return Response(
                {"status": "error", "message": "This account has been deactivated.",
                 "errors": {"identifier": ["Account is inactive."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.check_password(password):
            locked, remaining = otp_service.record_failed_login(identifier)
            if locked:
                return Response(
                    {"status": "error",
                     "message": f"Too many failed attempts. Account locked for {settings.LOGIN_LOCK_DURATION_MINUTES} minute(s)."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            return Response(
                {"status": "error", "message": f"Invalid credentials. {remaining} attempt(s) remaining.",
                 "errors": {"password": ["Incorrect password."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
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
        request=None,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Logged out",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={"status": "success", "message": "Logged out successfully."},
                    )
                ],
            ),
            401: _ERROR_401,
        },
        tags=["Authentication"],
        summary="Logout",
        description="Blacklists all outstanding tokens for the current user.",
    )
    def post(self, request):
        _blacklist_all_user_tokens(request.user)
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
                description="OTP sent for password reset",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={"status": "success",
                               "message": "OTP sent to your email. Please verify to reset your password.",
                               "data": {"email": "user@example.com", "otp_expires_in": "10 minutes"}},
                    )
                ],
            ),
            400: _ERROR_400,
            429: _ERROR_429,
        },
        tags=["Authentication"],
        summary="Password reset — step 1 (request OTP)",
        description="Sends a 6-digit OTP to the registered email. Call `/password/reset/verify-otp/` next.",
    )
    def post(self, request):
        serializer = serializers.PasswordResetRequestSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        email = serializer.validated_data["email"]
        if not User.objects.filter(email=email, is_email_verified=True).exists():
            return Response(
                {"status": "error", "message": "No account found for this email.",
                 "errors": {"email": ["No verified account found."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        eligible, err_msg = otp_service.check_resend_eligibility(email)
        if not eligible:
            return Response(
                {"status": "error", "message": err_msg},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        otp_code = otp_service.generate_and_store_otp(email, "password_reset")
        tasks.send_otp_email_task.delay(email, otp_code, "password_reset")
        logger.info("Password reset requested for %s", email)
        return Response(
            {"status": "success",
             "message": "OTP sent to your email. Please verify to reset your password.",
             "data": {"email": email, "otp_expires_in": f"{settings.OTP_EXPIRY_MINUTES} minutes"}},
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
                description="Existing user signed in via Google",
                examples=[
                    OpenApiExample(
                        "Login",
                        value={
                            "status": "success",
                            "message": "Signed in with Google successfully.",
                            "data": {
                                "user": {"id": 1, "email": "user@gmail.com", "username": "johndoe"},
                                "tokens": {"access": "eyJ...", "refresh": "eyJ..."},
                                "is_new_user": False,
                            },
                        },
                    )
                ],
            ),
            201: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="New user registered via Google",
                examples=[
                    OpenApiExample(
                        "Register",
                        value={
                            "status": "success",
                            "message": "Account created with Google successfully.",
                            "data": {
                                "user": {"id": 2, "email": "new@gmail.com", "username": "newuser"},
                                "tokens": {"access": "eyJ...", "refresh": "eyJ..."},
                                "is_new_user": True,
                            },
                        },
                    )
                ],
            ),
            400: _ERROR_400,
        },
        tags=["Authentication"],
        summary="Google OAuth — sign in or register",
        description=(
            "Accepts a Google ID token obtained from Google Sign-In on the client. "
            "Verifies it against Google's servers, then either signs in the existing user "
            "or creates a new account. Returns JWT tokens either way."
        ),
    )
    def post(self, request):
        serializer = serializers.GoogleAuthSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        token = serializer.validated_data["id_token"]
        try:
            payload = google_id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError as exc:
            logger.warning("Google token verification failed: %s", exc)
            return Response(
                {"status": "error", "message": "Invalid or expired Google token.",
                 "errors": {"id_token": ["Token verification failed."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        google_id = payload.get("sub")
        email = payload.get("email", "").strip().lower()
        if not email or not google_id:
            return Response(
                {"status": "error", "message": "Google token is missing required fields.",
                 "errors": {"id_token": ["Token did not contain email or sub."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            user = User.objects.get(google_id=google_id)
            if not user.is_active:
                return Response(
                    {"status": "error", "message": "This account has been deactivated."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            tokens = _get_tokens_for_user(user)
            logger.info("Google sign-in (existing google_id): %s", user.email)
            return Response(
                {
                    "status": "success",
                    "message": "Signed in with Google successfully.",
                    "data": {
                        "user": {"id": user.id, "email": user.email, "username": user.username},
                        "tokens": tokens,
                        "is_new_user": False,
                    },
                },
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            pass
        try:
            user = User.objects.get(email=email)
            if not user.is_active:
                return Response(
                    {"status": "error", "message": "This account has been deactivated."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.google_id = google_id
            user.is_email_verified = True
            user.save()
            tokens = _get_tokens_for_user(user)
            logger.info("Google sign-in (email match, google_id linked): %s", user.email)
            return Response(
                {
                    "status": "success",
                    "message": "Signed in with Google successfully.",
                    "data": {
                        "user": {"id": user.id, "email": user.email, "username": user.username},
                        "tokens": tokens,
                        "is_new_user": False,
                    },
                },
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            pass
        username = _generate_username_from_email(email)
        user = User(email=email, username=username, google_id=google_id, is_email_verified=True)
        user.set_unusable_password()
        user.save()
        tokens = _get_tokens_for_user(user)
        logger.info("New account created via Google: %s (@%s)", user.email, user.username)
        return Response(
            {
                "status": "success",
                "message": "Account created with Google successfully.",
                "data": {
                    "user": {"id": user.id, "email": user.email, "username": user.username},
                    "tokens": tokens,
                    "is_new_user": True,
                },
            },
            status=status.HTTP_201_CREATED,
        )