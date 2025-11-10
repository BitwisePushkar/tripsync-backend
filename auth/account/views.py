from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from account.serializers import (UserRegistrationSerializer, VerifyOTPSerializer, UserLoginSerializer,UserProfileSerializer, PasswordResetRequestSerializer, PasswordResetVerifySerializer)
from account.models import User
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from account.pagination import StandardResultsSetPagination
from django.db import models
from django.utils import timezone
from account.utils import send_otp_email

def get_tokens_for_user(user):
    if not user.is_active:
        raise AuthenticationFailed("User account is deactivated.")
    if not user.is_email_verified:
        raise AuthenticationFailed("Email verification required.")
    refresh = RefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}

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
                    OpenApiExample(
                        'Unexpected Error',
                        value={
                            'status': 'error',
                            'message': 'Registration failed',
                            'errors': 'Something went wrong while processing your request.'
                        }
                    )
                ]
            ),
            429: OpenApiResponse(
                description="Too many OTP attempts — account temporarily locked",
                examples=[
                    OpenApiExample(
                        'Too Many Attempts',
                        value={
                            'status': 'error',
                            'message': 'Too many failed attempts. Try again in 15 minutes.',
                            'errors': {
                                'email': ['Account temporarily locked']
                            }
                        }
                    )
                ]
            ),
            500: OpenApiResponse(
                description="Email service failure",
                examples=[
                    OpenApiExample(
                        'Email Service Unavailable',
                        value={
                            'status': 'error',
                            'message': 'Failed to send verification email. Please try again.',
                            'errors': {
                                'email': ['Email service unavailable']
                            }
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
                        time_remaining = (existing_user.otp_locked_until - timezone.now()).seconds // 60
                        return Response({'status': 'error','message': f'Too many failed attempts. Try again in {time_remaining} minutes.','errors': {'email': ['Account temporarily locked']}},status=status.HTTP_429_TOO_MANY_REQUESTS)
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
                                     'errors': {'email': ['Email service unavailable']}},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                return Response({'status': 'success','message': 'OTP sent to your email. Please verify to complete registration.',
                                 'data': {'email': user.email, 
                                 'otp_expires_in': '10 minutes'}},status=status.HTTP_200_OK)
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
                        name="Invalid or Expired OTP",
                        value={
                            "status": "error",
                            "message": "Invalid or expired OTP",
                            "errors": {"otp": ["The OTP you entered is invalid or expired"]},
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
                    OpenApiExample(
                        name="Unexpected Error",
                        value={
                            "status": "error",
                            "message": "OTP verification failed",
                            "errors": "Something went wrong while verifying OTP."
                        }
                    )
                ]
            ),
            429: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Too many failed OTP attempts — account temporarily locked",
                examples=[
                    OpenApiExample(
                        name="Too Many Attempts (Locked)",
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
        description="Verifies OTP."
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
                    return Response({'status': 'error','message': 'User not found or already verified.','errors': {'email': ['No pending registration found']}},status=status.HTTP_400_BAD_REQUEST)
                if user.is_otp_locked():
                    time_remaining = (user.otp_locked_until - timezone.now()).seconds // 60
                    return Response({'status': 'error','message': f'Too many failed attempts. Try again in {time_remaining} minutes.','errors': {'otp': ['Account temporarily locked']}},status=status.HTTP_429_TOO_MANY_REQUESTS)
                success, message, attempts_remaining = user.verify_otp(otp_code, 'registration')
                if success:
                    user.clear_otp()
                    return Response({'status': 'success','message': 'Email verified successfully!','data': {'user': {'id': user.id, 'email': user.email, 'is_email_verified': user.is_email_verified}}},status=status.HTTP_200_OK)
                else:
                    status_code = status.HTTP_429_TOO_MANY_REQUESTS if attempts_remaining == 0 else status.HTTP_400_BAD_REQUEST
                    return Response({'status': 'error', 'message': message,'errors': {'otp': [message]},'attempts_remaining': attempts_remaining},status=status_code)
        except Exception as e:
            return Response({'status': 'error', 'message': 'OTP verification failed', 'errors': str(e)},status=status.HTTP_400_BAD_REQUEST)

class ResendRegistrationOTPView(APIView):
    @extend_schema(
        request={
            'application/json': {'type': 'object','properties': {'email': {'type': 'string', 'format': 'email'}}}},
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="OTP resent successfully",
                examples=[
                    OpenApiExample(
                        name="Success Response",
                        value={
                            "status": "success",
                            "message": "OTP has been resent to your email.",
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
                description="Invalid request or missing email",
                examples=[
                    OpenApiExample(
                        name="Missing Email Field",
                        value={
                            "status": "error",
                            "message": "Email is required",
                            "errors": {"email": ["This field is required"]}
                        }
                    ),
                    OpenApiExample(
                        name="No Pending Registration",
                        value={
                            "status": "error",
                            "message": "Invalid request",
                            "errors": {"email": ["No pending registration found"]}
                        }
                    ),
                    OpenApiExample(
                        name="Unexpected Error",
                        value={
                            "status": "error",
                            "message": "Failed to resend OTP",
                            "errors": "Something went wrong while resending the OTP."
                        }
                    )
                ]
            ),
            429: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Account temporarily locked due to too many OTP attempts",
                examples=[
                    OpenApiExample(
                        name="Too Many Attempts",
                        value={
                            "status": "error",
                            "message": "Too many failed attempts. Try again in 15 minutes.",
                            "errors": {"otp": ["Account temporarily locked"]}
                        }
                    )
                ]
            ),
            500: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Email sending failed due to server error",
                examples=[
                    OpenApiExample(
                        name="Email Service Unavailable",
                        value={
                            "status": "error",
                            "message": "Failed to send OTP",
                            "errors": {"email": ["Email service unavailable"]}
                        }
                    )
                ]
            ),
        },
        tags=['Authentication'],
        summary="Resend registration OTP",
        description="Resends OTP for pending email verification."
    )
    def post(self, request):
        try:
            email = request.data.get('email', '').lower().strip()
            if not email:
                return Response({'status': 'error', 'message': 'Email is required','errors': {'email': ['This field is required']}},status=status.HTTP_400_BAD_REQUEST)
            try:
                user = User.objects.get(email=email, is_email_verified=False)
            except User.DoesNotExist:
                return Response({'status': 'error', 'message': 'Invalid request','errors': {'email': ['No pending registration found']}},status=status.HTTP_400_BAD_REQUEST)
            if user.is_otp_locked():
                time_remaining = (user.otp_locked_until - timezone.now()).seconds // 60
                return Response({'status': 'error','message': f'Too many failed attempts. Try again in {time_remaining} minutes.','errors': {'otp': ['Account temporarily locked']}},status=status.HTTP_429_TOO_MANY_REQUESTS)
            if user.last_otp_sent_at:
                time_since_last = (timezone.now() - user.last_otp_sent_at).total_seconds()
                if time_since_last < 120:
                    remaining = int(120 - time_since_last)
                    return Response({'status': 'error','message': f'Please wait {remaining} seconds before requesting another OTP.','errors': {'otp': ['OTP resend cooldown active']}},status=status.HTTP_429_TOO_MANY_REQUESTS)
            otp = user.generate_otp('registration')
            email_sent = send_otp_email(email, otp, purpose="verification")
            if not email_sent:
                return Response({'status': 'error', 'message': 'Failed to send OTP','errors': {'email': ['Email service unavailable']}},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({'status': 'success','message': 'OTP has been resent to your email.','data': {'email': email, 'otp_expires_in': '10 minutes'}},status=status.HTTP_200_OK)
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
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Invalid input or unexpected error",
                examples=[
                    OpenApiExample(
                        name="Invalid Email Format",
                        value={
                            "status": "error",
                            "message": "Login failed",
                            "errors": {"email": ["Enter a valid email address."]}
                        }
                    ),
                    OpenApiExample(
                        name="Unexpected Error",
                        value={
                            "status": "error",
                            "message": "Login failed",
                            "errors": "Something went wrong while processing the request."
                        }
                    )
                ]
            ),
            401: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Invalid credentials",
                examples=[
                    OpenApiExample(
                        name="Invalid Credentials",
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
                description="Access denied due to unverified or deactivated account",
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
        description="Authenticate user with email and password."
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
                        return Response({'status': 'error','message': 'Account is deactivated.','errors': {'account': ['Your account has been deactivated']}},status=status.HTTP_403_FORBIDDEN)
                    if not user.is_email_verified:
                        return Response({'status': 'error','message': 'Email verification required.','errors': {'account': ['Email not verified']}},status=status.HTTP_403_FORBIDDEN)
                    tokens = get_tokens_for_user(user)
                    return Response({'status': 'success','message': 'Login successful','data': {'user': {'id': user.id,'email': user.email,'is_email_verified': user.is_email_verified},'tokens': tokens}},status=status.HTTP_200_OK)
                else:
                    return Response({'status': 'error','message': 'Invalid credentials','errors': {'non_field_errors': ['Email or password is incorrect']}},status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'status': 'error', 'message': 'Login failed', 'errors': str(e)},status=status.HTTP_400_BAD_REQUEST)

class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]  
    @extend_schema(
        request={'application/json': {'type': 'object','properties': {'refresh': {'type': 'string', 'example': 'eyJ0eXAiOiJKV1QiLCJhbGc...'}},'required': ['refresh']}},
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Logged out successfully",
                examples=[
                    OpenApiExample(
                        name="Success Response",
                        value={
                            "status": "success",
                            "message": "Logged out successfully"
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Invalid or missing token",
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
                    ),
                    OpenApiExample(
                        name="Unexpected Error",
                        value={
                            "status": "error",
                            "message": "Logout failed",
                            "errors": "Something went wrong while processing the token."
                        }
                    )
                ]
            )
        },
        tags=['Authentication'],
        summary="Logout user",
        description="Blacklist the provided refresh token to log out the user."
    )
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({'status': 'error', 'message': 'Refresh token is required','errors': {'refresh': ['This field is required']}},status=status.HTTP_400_BAD_REQUEST)
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'status': 'success', 'message': 'Logged out successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'status': 'error', 'message': 'Logout failed', 'errors': str(e)},status=status.HTTP_400_BAD_REQUEST)

class PasswordResetRequestView(APIView):
    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Password reset OTP sent successfully",
                examples=[
                    OpenApiExample(
                        name="Success Response",
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
                description="Invalid request or validation error",
                examples=[
                    OpenApiExample(
                        name="Invalid Email",
                        value={
                            "status": "error",
                            "message": "Invalid request",
                            "errors": {"email": ["Unable to process request"]}
                        }
                    ),
                    OpenApiExample(
                        name="Unexpected Error",
                        value={
                            "status": "error",
                            "message": "Failed to send password reset OTP",
                            "errors": "Something went wrong"
                        }
                    )
                ]
            ),
            429: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Too many failed attempts",
                examples=[
                    OpenApiExample(
                        name="Locked Response",
                        value={
                            "status": "error",
                            "message": "Too many failed attempts. Try again in 10 minutes.",
                            "errors": {"otp": ["Account temporarily locked"]}
                        }
                    )
                ]
            ),
            500: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Email service unavailable",
                examples=[
                    OpenApiExample(
                        name="Email Error",
                        value={
                            "status": "error",
                            "message": "Failed to send OTP. Please try again.",
                            "errors": {"email": ["Email service unavailable"]}
                        }
                    )
                ]
            )
        },
        tags=['Authentication'],
        summary="Request password reset OTP",
        description="Sends OTP to user's email for password reset."
    )
    def post(self, request):
        try:
            serializer = PasswordResetRequestSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                email = serializer.validated_data.get('email')
                try:
                    user = User.objects.get(email=email, is_email_verified=True)
                except User.DoesNotExist:
                    return Response({'status': 'error', 'message': 'Invalid request','errors': {'email': ['Unable to process request']}},status=status.HTTP_400_BAD_REQUEST)
                if user.is_otp_locked():
                    time_remaining = (user.otp_locked_until - timezone.now()).seconds // 60
                    return Response({'status': 'error','message': f'Too many failed attempts. Try again in {time_remaining} minutes.','errors': {'otp': ['Account temporarily locked']}},status=status.HTTP_429_TOO_MANY_REQUESTS)
                if user.last_otp_sent_at:
                    time_since_last = (timezone.now() - user.last_otp_sent_at).total_seconds()
                    if time_since_last < 120:
                        remaining = int(120 - time_since_last)
                        return Response({'status': 'error','message': f'Please wait {remaining} seconds before requesting another OTP.','errors': {'otp': ['OTP resend cooldown active']}},status=status.HTTP_429_TOO_MANY_REQUESTS)
                otp = user.generate_otp('password_reset')
                email_sent = send_otp_email(email, otp, purpose="password_reset")
                if not email_sent:
                    return Response({'status': 'error', 'message': 'Failed to send OTP. Please try again.','errors': {'email': ['Email service unavailable']}},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                return Response({'status': 'success','message': 'Password reset OTP sent to your email.','data': {'email': email, 'otp_expires_in': '10 minutes'}},status=status.HTTP_200_OK)  
        except Exception as e:
            return Response({'status': 'error', 'message': 'Failed to send password reset OTP', 'errors': str(e)},status=status.HTTP_400_BAD_REQUEST)

class PasswordResetVerifyView(APIView):
    @extend_schema(
        request=PasswordResetVerifySerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Password reset successfully",
                examples=[
                    OpenApiExample(
                        name="Success Response",
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
                description="Invalid OTP, user not found, or validation error",
                examples=[
                    OpenApiExample(
                        name="Invalid OTP",
                        value={
                            "status": "error",
                            "message": "Invalid or expired OTP",
                            "errors": {"otp": ["The provided OTP is invalid or expired"]},
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
                    ),
                    OpenApiExample(
                        name="Unexpected Error",
                        value={
                            "status": "error",
                            "message": "Password reset failed",
                            "errors": "Something went wrong"
                        }
                    )
                ]
            ),
            429: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Too many failed attempts",
                examples=[
                    OpenApiExample(
                        name="Locked Response",
                        value={
                            "status": "error",
                            "message": "Too many failed attempts. Try again later.",
                            "errors": {"otp": ["Account temporarily locked"]}
                        }
                    )
                ]
            )
        },
        tags=['Authentication'],
        summary="Verify OTP and reset password",
        description="Verifies OTP and sets a new password."
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
                    return Response({'status': 'error', 'message': 'User not found','errors': {'email': ['User not found']}},status=status.HTTP_400_BAD_REQUEST)
                success, message, attempts_remaining = user.verify_otp(otp_code, 'password_reset') 
                if success:
                    user.set_password(new_password)
                    user.clear_otp()
                    user.save()
                    return Response({'status': 'success','message': 'Password has been reset successfully.','data': {'email': user.email}},status=status.HTTP_200_OK)
                else:
                    status_code = status.HTTP_429_TOO_MANY_REQUESTS if attempts_remaining == 0 else status.HTTP_400_BAD_REQUEST
                    return Response({'status': 'error', 'message': message,'errors': {'otp': [message]},'attempts_remaining': attempts_remaining},status=status_code) 
        except Exception as e:
            return Response({'status': 'error', 'message': 'Password reset failed', 'errors': str(e)},status=status.HTTP_400_BAD_REQUEST)