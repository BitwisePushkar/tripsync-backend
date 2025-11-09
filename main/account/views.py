from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError as DRFValidationError
from account.serializers import (UserRegistrationSerializer,VerifyOTPSerializer,UserLoginSerializer,
                                 PasswordResetRequestSerializer,PasswordResetVerifySerializer,)
from account.models import User
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from django.utils import timezone
from account.utils import send_otp_email

def get_tokens_for_user(user):
    if not user.is_active:
        raise AuthenticationFailed("User account is deactivated.")
    if not user.is_email_verified:
        raise AuthenticationFailed("Email verification required.")
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh)
    }

class UserRegistrationView(APIView):
    @extend_schema(
        request=UserRegistrationSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="OTP sent successfully",
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={
                            'status': 'success',
                            'message': 'OTP sent to your email. Please verify to complete registration.',
                            'data': {
                                'email': 'user@gmail.com',
                                'otp_expires_in': '10 minutes'
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Validation or unexpected error",
                examples=[
                    OpenApiExample(
                        'Invalid Input',
                        value={
                            'status': 'error',
                            'message': 'Registration failed',
                            'errors': {
                                'email': ['Enter a valid email address.'],
                                'password': ['Password must be at least 8 characters long.']
                            }
                        }
                    ),
                ]
            ),
            429: OpenApiResponse(
                description="Too many OTP attempts or resend cooldown active",
                examples=[
                    OpenApiExample(
                        'Account Locked',
                        value={
                            'status': 'error',
                            'message': 'Too many failed attempts. Try again in 15 minutes.',
                            'errors': {'email': ['Account temporarily locked']}
                        }
                    ),
                    OpenApiExample(
                        'Resend Cooldown Active',
                        value={
                            'status': 'error',
                            'message': 'Please wait 85 seconds before requesting another OTP.',
                            'errors': {'otp': ['OTP resend cooldown active']}
                        }
                    )
                ]
            ),
            503: OpenApiResponse(
                description="Email service failure",
                examples=[
                    OpenApiExample(
                        'Email Service Unavailable',
                        value={
                            'status': 'error',
                            'message': 'Failed to send verification email. Please try again.',
                            'errors': {'email': ['Email service unavailable']}
                        }
                    )
                ]
            ),
        },
        tags=['Authentication'],
        summary="Register a new user",
        description="Creates user and sends OTP for email verification."
    )
    def post(self, request, format=None):
        try:
            serializer = UserRegistrationSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                email = serializer.validated_data.get('email')
                password = serializer.validated_data.get('password')
                User.objects.filter(email=email,is_email_verified=False,otp_exp__lt=timezone.now()).delete()
                existing_user = User.objects.filter(email=email, is_email_verified=False).first()
                if existing_user:
                    if existing_user.is_otp_locked():
                        time_remaining = int((existing_user.otp_locked_until - timezone.now()).total_seconds() // 60)
                        return Response({'status': 'error','message': f'Too many failed attempts. Try again in {time_remaining} minutes.',
                                         'errors': {'email': ['Account temporarily locked']}},status=status.HTTP_429_TOO_MANY_REQUESTS)
                    if existing_user.last_otp_sent_at:
                        time_since_last = (timezone.now() - existing_user.last_otp_sent_at).total_seconds()
                        if time_since_last < 120:
                            remaining = int(120 - time_since_last)
                            return Response({'status': 'error','message': f'Please wait {remaining} seconds before requesting another OTP.',
                                             'errors': {'otp': ['OTP resend cooldown active']}},status=status.HTTP_429_TOO_MANY_REQUESTS)
                    existing_user.set_password(password)
                    existing_user.save()
                    otp = existing_user.generate_otp('registration')
                    user = existing_user
                else:
                    user = User.objects.create_user(email=email, password=password)
                    otp = user.generate_otp('registration')
                email_sent = send_otp_email(user.email, otp, purpose="verification")
                if not email_sent:
                    if not existing_user:
                        user.delete()
                    return Response({'status': 'error','message': 'Failed to send verification email. Please try again.',
                                     'errors': {'email': ['Email service unavailable']}},status=status.HTTP_503_SERVICE_UNAVAILABLE)
                return Response({'status': 'success','message': 'OTP sent to your email. Please verify to complete registration.',
                                 'data': {'email': user.email,'otp_expires_in': '10 minutes'}},status=status.HTTP_200_OK)
        except DRFValidationError:
            raise
        except Exception as e:
            return Response({'status': 'error', 'message': 'Registration failed', 'errors': str(e)},status=status.HTTP_400_BAD_REQUEST)

class VerifyRegistrationOTPView(APIView):
    @extend_schema(
        request=VerifyOTPSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Email verified successfully",
                examples=[
                    OpenApiExample(
                        name="Success Response",
                        value={
                            "status": "success",
                            "message": "Email verified successfully!",
                            "data": {
                                "user": {
                                    "id": 1,
                                    "email": "user@example.com",
                                    "is_email_verified": True
                                }
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Invalid OTP, expired OTP, or user not found",
                examples=[
                    OpenApiExample(
                        name="Invalid OTP",
                        value={
                            "status": "error",
                            "message": "Invalid OTP. 2 attempt(s) remaining.",
                            "errors": {"otp": ["Invalid OTP. 2 attempt(s) remaining."]},
                            "attempts_remaining": 2
                        }
                    ),
                    OpenApiExample(
                        name="User Not Found or Already Verified",
                        value={
                            "status": "error",
                            "message": "User not found or already verified.",
                            "errors": {"email": ["No pending registration found"]}
                        }
                    ),
                ]
            ),
            429: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Too many failed OTP attempts — account temporarily locked",
                examples=[
                    OpenApiExample(
                        name="Account Locked",
                        value={
                            "status": "error",
                            "message": "Too many failed attempts. Try again in 15 minutes.",
                            "errors": {"otp": ["Account temporarily locked"]}
                        }
                    )
                ]
            )
        },
        tags=["Authentication"],
        summary="Verify registration OTP",
        description="Verifies the 6-digit OTP for email registration."
    )
    def post(self, request):
        try:
            serializer = VerifyOTPSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                email = serializer.validated_data.get('email')
                otp_code = serializer.validated_data.get('otp')
                try:
                    user = User.objects.get(email=email, is_email_verified=False)
                except User.DoesNotExist:
                    return Response({'status': 'error','message': 'User not found or already verified.',
                                     'errors': {'email': ['No pending registration found']}},status=status.HTTP_400_BAD_REQUEST)
                if user.is_otp_locked():
                    time_remaining = int((user.otp_locked_until - timezone.now()).total_seconds() // 60)
                    return Response({'status': 'error','message': f'Too many failed attempts. Try again in {time_remaining} minutes.',
                                     'errors': {'otp': ['Account temporarily locked']}},status=status.HTTP_429_TOO_MANY_REQUESTS)
                success, message, attempts_remaining = user.verify_otp(otp_code, 'registration')
                if success:
                    user.clear_otp()
                    return Response({'status': 'success','message': 'Email verified successfully!',
                                     'data': {'user': {'id': user.id,'email': user.email,'is_email_verified': user.is_email_verified}}},
                                     status=status.HTTP_200_OK)
                else:
                    status_code = status.HTTP_429_TOO_MANY_REQUESTS if attempts_remaining == 0 else status.HTTP_400_BAD_REQUEST
                    return Response({'status': 'error','message': message,'errors': {'otp': [message]},
                                     'attempts_remaining': attempts_remaining},status=status_code)
        except DRFValidationError:
            raise
        except Exception as e:
            return Response({'status': 'error', 'message': 'OTP verification failed', 'errors': str(e)},status=status.HTTP_400_BAD_REQUEST)

class ResendOTPView(APIView):
    @extend_schema(
        tags=['Authentication'],
        summary="Resend OTP (registration or password reset)",
        description=("Resends an OTP to the given email. Automatically detects the OTP"),
        request={
            'application/json': {
                'type': 'object',
                'required': ['email'],
                'properties': {
                    'email': {
                        'type': 'string',
                        'format': 'email',
                        'example': 'user@example.com'
                    }
                }
            }
        },
        responses={
            200: OpenApiResponse(
                description="OTP resent successfully",
                examples=[
                    OpenApiExample(
                        name="Success — Registration OTP Resent",
                        summary="Unverified account → registration OTP sent",
                        value={
                            "status": "success",
                            "message": "OTP has been resent to your email.",
                            "data": {
                                "email": "user@example.com",
                                "otp_type": "registration",
                                "otp_expires_in": "10 minutes"
                            }
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name="Success — Password Reset OTP Resent",
                        summary="Verified account → password reset OTP sent",
                        value={
                            "status": "success",
                            "message": "OTP has been resent to your email.",
                            "data": {
                                "email": "user@example.com",
                                "otp_type": "password_reset",
                                "otp_expires_in": "10 minutes"
                            }
                        },
                        response_only=True,
                    ),
                ]
            ),
            400: OpenApiResponse(
                description="Email missing or no eligible account found",
                examples=[
                    OpenApiExample(
                        name="Error — Email Required",
                        value={
                            "status": "error",
                            "message": "Email is required",
                            "errors": {"email": ["This field is required"]}
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name="Error — No Eligible Account",
                        summary="Email unknown entirely",
                        value={
                            "status": "error",
                            "message": "Invalid request",
                            "errors": {"email": ["Unable to process request"]}
                        },
                        response_only=True,
                    ),
                ]
            ),
            429: OpenApiResponse(
                description="Cooldown active or account locked",
                examples=[
                    OpenApiExample(
                        name="Error — Resend Cooldown",
                        value={
                            "status": "error",
                            "message": "Please wait 85 seconds before requesting another OTP.",
                            "errors": {"otp": ["OTP resend cooldown active"]}
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name="Error — Account Locked",
                        value={
                            "status": "error",
                            "message": "Too many failed attempts. Try again in 47 minutes.",
                            "errors": {"otp": ["Account temporarily locked"]}
                        },
                        response_only=True,
                    ),
                ]
            ),
            503: OpenApiResponse(
                description="Email delivery failed",
                examples=[
                    OpenApiExample(
                        name="Error — SMTP Failure",
                        value={
                            "status": "error",
                            "message": "Failed to send OTP",
                            "errors": {"email": ["Email service unavailable"]}
                        },
                        response_only=True,
                    ),
                ]
            ),
        },
    )
    def post(self, request):
        try:
            email = request.data.get('email', '').lower().strip()
            if not email:
                return Response({'status': 'error','message': 'Email is required','errors': {'email': ['This field is required']}},
                                status=status.HTTP_400_BAD_REQUEST)
            user = (User.objects.filter(email=email, is_email_verified=False).first() or
                    User.objects.filter(email=email, is_email_verified=True).first())
            if not user:
                return Response({'status': 'error','message': 'Invalid request','errors': {'email': ['Unable to process request']}},
                                status=status.HTTP_400_BAD_REQUEST)
            otp_type = 'registration' if not user.is_email_verified else 'password_reset'
            email_purpose = 'verification' if otp_type == 'registration' else 'password_reset'
            if user.is_otp_locked():
                time_remaining = int((user.otp_locked_until - timezone.now()).total_seconds() // 60)
                return Response({'status': 'error','message': f'Too many failed attempts. Try again in {time_remaining} minutes.',
                                 'errors': {'otp': ['Account temporarily locked']}},status=status.HTTP_429_TOO_MANY_REQUESTS)
            if user.last_otp_sent_at:
                time_since_last = (timezone.now() - user.last_otp_sent_at).total_seconds()
                if time_since_last < 120:
                    remaining = int(120 - time_since_last)
                    return Response({'status': 'error','message': f'Please wait {remaining} seconds before requesting another OTP.',
                                     'errors': {'otp': ['OTP resend cooldown active']}},status=status.HTTP_429_TOO_MANY_REQUESTS)
            otp = user.generate_otp(otp_type)
            email_sent = send_otp_email(email, otp, purpose=email_purpose)
            if not email_sent:
                return Response({'status': 'error','message': 'Failed to send OTP','errors': {'email': ['Email service unavailable']}},
                                status=status.HTTP_503_SERVICE_UNAVAILABLE)
            return Response({'status': 'success','message': 'OTP has been resent to your email.',
                             'data': {'email': email,'otp_type': otp_type,'otp_expires_in': '10 minutes'}},
                             status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'status': 'error', 'message': 'Failed to resend OTP', 'errors': str(e)},status=status.HTTP_400_BAD_REQUEST)

class UserLoginView(APIView):
    @extend_schema(
        request=UserLoginSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Login successful",
                examples=[
                    OpenApiExample(
                        name="Success Response",
                        value={
                            "status": "success",
                            "message": "Login successful",
                            "data": {
                                "user": {
                                    "id": 1,
                                    "email": "user@example.com",
                                    "is_email_verified": True
                                },
                                "tokens": {
                                    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                                    "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
                                }
                            }
                        }
                    )
                ]
            ),
            401: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Invalid credentials",
                examples=[
                    OpenApiExample(
                        name="Wrong Email or Password",
                        value={
                            "status": "error",
                            "message": "Invalid credentials",
                            "errors": {"non_field_errors": ["Email or password is incorrect"]}
                        }
                    )
                ]
            ),
            403: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Account not verified or deactivated",
                examples=[
                    OpenApiExample(
                        name="Email Not Verified",
                        value={
                            "status": "error",
                            "message": "Email verification required.",
                            "errors": {"account": ["Email not verified"]}
                        }
                    ),
                    OpenApiExample(
                        name="Account Deactivated",
                        value={
                            "status": "error",
                            "message": "Account is deactivated.",
                            "errors": {"account": ["Your account has been deactivated"]}
                        }
                    )
                ]
            ),
        },
        tags=["Authentication"],
        summary="Login user",
        description="Authenticate with email and password. Returns JWT tokens."
    )
    def post(self, request, format=None):
        try:
            serializer = UserLoginSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                email = serializer.validated_data.get('email')
                password = serializer.validated_data.get('password')
                user = authenticate(request, email=email, password=password)
                if user is not None:
                    if not user.is_active:
                        return Response({'status': 'error','message': 'Account is deactivated.',
                                         'errors': {'account': ['Your account has been deactivated']}},status=status.HTTP_403_FORBIDDEN)
                    if not user.is_email_verified:
                        return Response({'status': 'error','message': 'Email verification required.',
                                         'errors': {'account': ['Email not verified']}},status=status.HTTP_403_FORBIDDEN)
                    tokens = get_tokens_for_user(user)
                    return Response({'status': 'success','message': 'Login successful','data': {
                        'user': {'id': user.id,'email': user.email,'is_email_verified': user.is_email_verified},
                        'tokens': tokens}},status=status.HTTP_200_OK)
                else:
                    return Response({'status': 'error','message': 'Invalid credentials','errors': {'non_field_errors': ['Email or password is incorrect']}},
                                    status=status.HTTP_401_UNAUTHORIZED)
        except DRFValidationError:
            raise
        except Exception as e:
            return Response({'status': 'error', 'message': 'Login failed', 'errors': str(e)},status=status.HTTP_400_BAD_REQUEST)

class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        request={
            'application/json': {
                'type': 'object',
                'properties': {'refresh': {'type': 'string', 'example': 'eyJ0eXAiOiJKV1QiLCJhbGc...'}},
                'required': ['refresh']
            }
        },
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Logged out successfully",
                examples=[
                    OpenApiExample(
                        name="Success",
                        value={"status": "success", "message": "Logged out successfully"}
                    )
                ]
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Missing or invalid token",
                examples=[
                    OpenApiExample(
                        name="Missing Token",
                        value={
                            "status": "error",
                            "message": "Refresh token is required",
                            "errors": {"refresh": ["This field is required"]}
                        }
                    ),
                    OpenApiExample(
                        name="Invalid Token",
                        value={
                            "status": "error",
                            "message": "Logout failed",
                            "errors": {"refresh": ["Invalid or expired token"]}
                        }
                    )
                ]
            ),
            401: OpenApiResponse(description="Missing or invalid Authorization header"),
        },
        tags=['Authentication'],
        summary="Logout user",
        description="Blacklists the refresh token. Requires Bearer token in Authorization header."
    )
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({'status': 'error','message': 'Refresh token is required','errors': {'refresh': ['This field is required']}},
                                status=status.HTTP_400_BAD_REQUEST)
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'status': 'success', 'message': 'Logged out successfully'},status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'status': 'error', 'message': 'Logout failed', 'errors': str(e)},status=status.HTTP_400_BAD_REQUEST)

class PasswordResetRequestView(APIView):
    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Password reset OTP sent",
                examples=[
                    OpenApiExample(
                        name="Success",
                        value={
                            "status": "success",
                            "message": "Password reset OTP sent to your email.",
                            "data": {
                                "email": "user@example.com",
                                "otp_expires_in": "10 minutes"
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Email not registered or validation error",
                examples=[
                    OpenApiExample(
                        name="Not Found",
                        value={
                            "status": "error",
                            "message": "Invalid request",
                            "errors": {"email": ["Unable to process request"]}
                        }
                    )
                ]
            ),
            429: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Locked or cooldown active",
                examples=[
                    OpenApiExample(
                        name="Locked",
                        value={
                            "status": "error",
                            "message": "Too many failed attempts. Try again in 10 minutes.",
                            "errors": {"otp": ["Account temporarily locked"]}
                        }
                    ),
                    OpenApiExample(
                        name="Cooldown",
                        value={
                            "status": "error",
                            "message": "Please wait 85 seconds before requesting another OTP.",
                            "errors": {"otp": ["OTP resend cooldown active"]}
                        }
                    )
                ]
            ),
            503: OpenApiResponse(description="Email service unavailable"),
        },
        tags=['Authentication'],
        summary="Request password reset OTP",
        description="Sends OTP to verified email for password reset."
    )
    def post(self, request):
        try:
            serializer = PasswordResetRequestSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                email = serializer.validated_data.get('email')
                try:
                    user = User.objects.get(email=email, is_email_verified=True)
                except User.DoesNotExist:
                    return Response({'status': 'error','message': 'Invalid request','errors': {'email': ['Unable to process request']}},
                                    status=status.HTTP_400_BAD_REQUEST)
                if user.is_otp_locked():
                    time_remaining = int((user.otp_locked_until - timezone.now()).total_seconds() // 60)
                    return Response({'status': 'error','message': f'Too many failed attempts. Try again in {time_remaining} minutes.',
                                     'errors': {'otp': ['Account temporarily locked']}},status=status.HTTP_429_TOO_MANY_REQUESTS)
                if user.last_otp_sent_at:
                    time_since_last = (timezone.now() - user.last_otp_sent_at).total_seconds()
                    if time_since_last < 120:
                        remaining = int(120 - time_since_last)
                        return Response({'status': 'error','message': f'Please wait {remaining} seconds before requesting another OTP.',
                                         'errors': {'otp': ['OTP resend cooldown active']}},status=status.HTTP_429_TOO_MANY_REQUESTS)
                otp = user.generate_otp('password_reset')
                email_sent = send_otp_email(email, otp, purpose="password_reset")
                if not email_sent:
                    return Response({'status': 'error','message': 'Failed to send OTP. Please try again.',
                                     'errors': {'email': ['Email service unavailable']}},status=status.HTTP_503_SERVICE_UNAVAILABLE)
                return Response({'status': 'success','message': 'Password reset OTP sent to your email.',
                                 'data': {'email': email, 'otp_expires_in': '10 minutes'}},status=status.HTTP_200_OK)
        except DRFValidationError:
            raise
        except Exception as e:
            return Response({'status': 'error', 'message': 'Failed to send password reset OTP', 'errors': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

class PasswordResetVerifyView(APIView):
    @extend_schema(
        request=PasswordResetVerifySerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Password reset successfully",
                examples=[
                    OpenApiExample(
                        name="Success",
                        value={
                            "status": "success",
                            "message": "Password has been reset successfully.",
                            "data": {"email": "user@example.com"}
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Invalid OTP or user not found",
                examples=[
                    OpenApiExample(
                        name="Invalid OTP",
                        value={
                            "status": "error",
                            "message": "Invalid OTP. 1 attempt(s) remaining.",
                            "errors": {"otp": ["Invalid OTP. 1 attempt(s) remaining."]},
                            "attempts_remaining": 1
                        }
                    ),
                    OpenApiExample(
                        name="User Not Found",
                        value={
                            "status": "error",
                            "message": "User not found",
                            "errors": {"email": ["User not found"]}
                        }
                    )
                ]
            ),
            429: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Too many failed attempts",
                examples=[
                    OpenApiExample(
                        name="Locked",
                        value={
                            "status": "error",
                            "message": "Too many failed attempts. Account locked for 1 hour(s).",
                            "errors": {"otp": ["Too many failed attempts. Account locked for 1 hour(s)."]},
                            "attempts_remaining": 0
                        }
                    )
                ]
            )
        },
        tags=['Authentication'],
        summary="Verify OTP and reset password",
        description="Verifies the password reset OTP and updates the user's password."
    )
    def post(self, request):
        try:
            serializer = PasswordResetVerifySerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                email = serializer.validated_data.get('email')
                otp_code = serializer.validated_data.get('otp')
                new_password = serializer.validated_data.get('new_password')
                try:
                    user = User.objects.get(email=email, is_email_verified=True)
                except User.DoesNotExist:
                    return Response({'status': 'error','message': 'User not found','errors': {'email': ['User not found']}},
                                    status=status.HTTP_400_BAD_REQUEST)
                success, message, attempts_remaining = user.verify_otp(otp_code, 'password_reset')
                if success:
                    user.set_password(new_password)
                    user.clear_otp()
                    user.save()
                    return Response({'status': 'success','message': 'Password has been reset successfully.',
                                     'data': {'email': user.email}},status=status.HTTP_200_OK)
                else:
                    status_code = status.HTTP_429_TOO_MANY_REQUESTS if attempts_remaining == 0 else status.HTTP_400_BAD_REQUEST
                    return Response({'status': 'error','message': message,'errors': {'otp': [message]},
                                     'attempts_remaining': attempts_remaining},status=status_code)
        except DRFValidationError:
            raise
        except Exception as e:
            return Response({'status': 'error', 'message': 'Password reset failed', 'errors': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)