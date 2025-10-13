from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from account.serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserProfileSerializer,
    VerifyEmailOTPSerializer, PasswordResetVerifyOTPSerializer, 
    PasswordResetConfirmSerializer
)
from account.models import User
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from account.pagination import StandardResultsSetPagination
from django.db import models
from django.utils import timezone


def get_tokens_for_user(user):
    if not user.is_active:
        raise AuthenticationFailed("User account is deactivated.")
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class UserRegistrationView(APIView):
    @extend_schema(
        request=UserRegistrationSerializer,
        responses={
            201: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="User registered successfully",
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={
                            'status': 'success',
                            'message': 'Registration successful! Please verify your email.',
                            'data': {
                                'user': {
                                    'id': 1,
                                    'email': 'user@example.com',
                                    'name': 'John Doe',
                                    'phone_number': '+919876543210'
                                },
                                'tokens': {
                                    'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGc...',
                                    'access': 'eyJ0eXAiOiJKV1QiLCJhbGc...'
                                }
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(description="Validation error"),
        },
        tags=['Authentication'],
        summary="Register a new user",
        description="Create a new user account with email, password, name, and phone number"
    )
    def post(self, request, format=None):
        try:
            serializer = UserRegistrationSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                user = serializer.save()
                tokens = get_tokens_for_user(user)
                otp = user.generate_otp()
                from account.utils import send_otp_email
                email_sent = send_otp_email(user.email, otp, purpose="verification")
                
                if not email_sent:
                    print(f"WARNING: Failed to send OTP email to {user.email}")
                
                return Response({
                    'status': 'success',
                    'message': 'Registration successful! Please verify your email with the OTP sent.',
                    'data': {
                        'user': {
                            'id': user.id,
                            'email': user.email,
                            'name': user.name,
                            'phone_number': user.phone_number,
                            'is_email_verified': user.is_email_verified
                        },
                        'tokens': tokens
                    }
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            print(f"Registration error: {str(e)}")
            return Response({
                'status': 'error',
                'message': 'Registration failed',
                'errors': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class UserLoginView(APIView):
    @extend_schema(
        request=UserLoginSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="User logged in successfully",
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={
                            'status': 'success',
                            'message': 'Login successful',
                            'data': {
                                'user': {
                                    'id': 1,
                                    'email': 'user@example.com',
                                    'name': 'John Doe'
                                },
                                'tokens': {
                                    'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGc...',
                                    'access': 'eyJ0eXAiOiJKV1QiLCJhbGc...'
                                }
                            }
                        }
                    )
                ]
            ),
            401: OpenApiResponse(description="Invalid credentials"),
        },
        tags=['Authentication'],
        summary="Login user",
        description="Authenticate user with email and password, returns JWT tokens"
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
                        return Response({
                            'status': 'error',
                            'message': 'Account is deactivated. Please contact support.',
                            'errors': {'account': ['Your account has been deactivated']}
                        }, status=status.HTTP_403_FORBIDDEN)
                    
                    tokens = get_tokens_for_user(user)
                    return Response({
                        'status': 'success',
                        'message': 'Login successful',
                        'data': {
                            'user': {
                                'id': user.id,
                                'email': user.email,
                                'name': user.name,
                                'phone_number': user.phone_number,
                                'is_email_verified': user.is_email_verified
                            },
                            'tokens': tokens
                        }
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'status': 'error',
                        'message': 'Invalid credentials',
                        'errors': {'non_field_errors': ['Email or password is incorrect']}
                    }, status=status.HTTP_401_UNAUTHORIZED)
                    
        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Login failed',
                'errors': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        request={'application/json': {'type': 'object', 'properties': {'refresh': {'type': 'string'}}}},
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Logged out successfully",
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={
                            'status': 'success',
                            'message': 'Logged out successfully'
                        }
                    )
                ]
            ),
            400: OpenApiResponse(description="Invalid token"),
        },
        tags=['Authentication'],
        summary="Logout user",
        description="Blacklist the refresh token to logout user"
    )
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({
                    'status': 'error',
                    'message': 'Refresh token is required',
                    'errors': {'refresh': ['This field is required']}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response({
                'status': 'success',
                'message': 'Logged out successfully'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Logout failed',
                'errors': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class UserListView(ListAPIView):
    queryset = User.objects.all().order_by('-created_at')
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = StandardResultsSetPagination
    
    @extend_schema(
        parameters=[
            OpenApiParameter(name='page', type=int, location=OpenApiParameter.QUERY, description='Page number', required=False),
            OpenApiParameter(name='page_size', type=int, location=OpenApiParameter.QUERY, description='Number of results per page (max 100)', required=False),
            OpenApiParameter(name='search', type=str, location=OpenApiParameter.QUERY, description='Search by name or email', required=False),
            OpenApiParameter(name='is_verified', type=bool, location=OpenApiParameter.QUERY, description='Filter by email verification status', required=False),
        ],
        responses={
            200: OpenApiResponse(
                response=UserProfileSerializer(many=True),
                description="List of users with pagination"
            ),
            401: OpenApiResponse(description="Unauthorized - Token required"),
            403: OpenApiResponse(description="Forbidden - Admin access only"),
        },
        tags=['User Management'],
        summary="List all users (Admin only)",
        description="Retrieve paginated list of all registered users. Supports search and filtering."
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(models.Q(name__icontains=search) | models.Q(email__icontains=search))
        
        is_verified = self.request.query_params.get('is_verified', None)
        if is_verified is not None:
            is_verified_bool = is_verified.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(is_email_verified=is_verified_bool)
        
        return queryset


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={
            200: OpenApiResponse(
                response=UserProfileSerializer,
                description="User profile retrieved successfully"
            ),
            401: OpenApiResponse(description="Unauthorized - Token required"),
        },
        tags=['User Management'],
        summary="Get current user profile",
        description="Retrieve the profile of the currently authenticated user"
    )
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response({'status': 'success', 'data': serializer.data}, status=status.HTTP_200_OK)


class SendEmailOTPView(APIView):
    @extend_schema(
        request={'application/json': {'type': 'object', 'properties': {'email': {'type': 'string', 'format': 'email'}}}},
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="OTP sent successfully"
            ),
            400: OpenApiResponse(description="Validation error"),
        },
        tags=['Email Verification'],
        summary="Send OTP for email verification",
        description="Sends a 6-digit OTP to the user's email for verification"
    )
    def post(self, request):
        try:
            email = request.data.get('email', '').lower()
            
            if not email:
                return Response({
                    'status': 'error',
                    'message': 'Email is required',
                    'errors': {'email': ['This field is required']}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({
                    'status': 'error',
                    'message': 'Invalid request',
                    'errors': {'email': ['Unable to process request']}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if user.is_email_verified:
                return Response({
                    'status': 'error',
                    'message': 'Email already verified',
                    'errors': {'email': ['This email is already verified']}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if user.is_otp_locked():
                time_remaining = (user.otp_locked_until - timezone.now()).seconds // 60
                return Response({
                    'status': 'error',
                    'message': f'Too many failed attempts. Try again in {time_remaining} minutes.',
                    'errors': {'otp': ['Account temporarily locked']}
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            otp = user.generate_otp()
            
            from account.utils import send_otp_email
            email_sent = send_otp_email(email, otp, purpose="verification")
            
            if not email_sent:
                print(f"ERROR: Failed to send OTP email to {email}")
                return Response({
                    'status': 'error',
                    'message': 'Failed to send OTP email. Please try again.',
                    'errors': {'email': ['Email service temporarily unavailable']}
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            print(f"SUCCESS: OTP sent to {email} - OTP: {otp}")
            
            return Response({
                'status': 'success',
                'message': 'OTP has been sent to your email address.',
                'data': {'email': email, 'otp_expires_in': '10 minutes'}
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"SendEmailOTP error: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                'status': 'error',
                'message': 'Failed to send OTP',
                'errors': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailOTPView(APIView):
    @extend_schema(
        request=VerifyEmailOTPSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Email verified successfully"
            ),
            400: OpenApiResponse(description="Invalid or expired OTP"),
        },
        tags=['Email Verification'],
        summary="Verify email with OTP",
        description="Verifies the user's email address using the OTP code with attempt tracking"
    )
    def post(self, request):
        try:
            email = request.data.get('email', '').lower()
            otp_code = request.data.get('otp', '')
            
            if not email or not otp_code:
                return Response({
                    'status': 'error',
                    'message': 'Email and OTP are required',
                    'errors': {'non_field_errors': ['Both email and OTP are required']}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({
                    'status': 'error',
                    'message': 'User not found',
                    'errors': {'email': ['User not found']}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if user.is_email_verified:
                return Response({
                    'status': 'error',
                    'message': 'Email is already verified',
                    'errors': {'email': ['Email is already verified']}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            success, message, attempts_remaining = user.verify_otp(otp_code)
            
            if success:
                user.is_email_verified = True
                user.clear_otp()
                
                return Response({
                    'status': 'success',
                    'message': 'Email verified successfully!',
                    'data': {'email': user.email, 'is_email_verified': user.is_email_verified}
                }, status=status.HTTP_200_OK)
            else:
                status_code = status.HTTP_429_TOO_MANY_REQUESTS if attempts_remaining == 0 else status.HTTP_400_BAD_REQUEST
                return Response({
                    'status': 'error',
                    'message': message,
                    'errors': {'otp': [message]},
                    'attempts_remaining': attempts_remaining
                }, status=status_code)
                
        except Exception as e:
            print(f"VerifyEmailOTP error: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                'status': 'error',
                'message': 'Email verification failed',
                'errors': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetRequestView(APIView):
    @extend_schema(
        request={'application/json': {'type': 'object', 'properties': {'email': {'type': 'string', 'format': 'email'}}}},
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Password reset OTP sent"
            ),
            400: OpenApiResponse(description="Validation error"),
        },
        tags=['Password Reset'],
        summary="Request password reset OTP",
        description="Sends OTP to user's email for password reset"
    )
    def post(self, request):
        try:
            email = request.data.get('email', '').lower()
            
            if not email:
                return Response({
                    'status': 'error',
                    'message': 'Email is required',
                    'errors': {'email': ['This field is required']}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({
                    'status': 'error',
                    'message': 'Invalid request',
                    'errors': {'email': ['Unable to process request']}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if user.is_otp_locked():
                time_remaining = (user.otp_locked_until - timezone.now()).seconds // 60
                return Response({
                    'status': 'error',
                    'message': f'Too many failed attempts. Try again in {time_remaining} minutes.',
                    'errors': {'otp': ['Account temporarily locked']}
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            otp = user.generate_otp()
            
            from account.utils import send_otp_email
            email_sent = send_otp_email(email, otp, purpose="password_reset")
            
            if not email_sent:
                print(f"ERROR: Failed to send password reset OTP to {email}")
                return Response({
                    'status': 'error',
                    'message': 'Failed to send OTP email. Please try again.',
                    'errors': {'email': ['Email service temporarily unavailable']}
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            print(f"SUCCESS: Password reset OTP sent to {email} - OTP: {otp}")
            
            return Response({
                'status': 'success',
                'message': 'Password reset OTP has been sent to your email.',
                'data': {'email': email, 'next_step': 'Verify OTP to proceed with password reset'}
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"PasswordResetRequest error: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                'status': 'error',
                'message': 'Failed to send password reset OTP',
                'errors': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetVerifyOTPView(APIView):
    @extend_schema(
        request=PasswordResetVerifyOTPSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="OTP verified successfully"
            ),
            400: OpenApiResponse(description="Invalid or expired OTP"),
        },
        tags=['Password Reset'],
        summary="Verify password reset OTP",
        description="Verifies the OTP for password reset with attempt tracking"
    )
    def post(self, request):
        try:
            email = request.data.get('email', '').lower()
            otp_code = request.data.get('otp', '')
            
            if not email or not otp_code:
                return Response({
                    'status': 'error',
                    'message': 'Email and OTP are required',
                    'errors': {'non_field_errors': ['Both email and OTP are required']}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({
                    'status': 'error',
                    'message': 'User not found',
                    'errors': {'email': ['User not found']}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            success, message, attempts_remaining = user.verify_otp(otp_code)
            
            if success:
                return Response({
                    'status': 'success',
                    'message': 'OTP verified successfully. You can now reset your password.',
                    'data': {'email': user.email, 'otp_verified': True, 'next_step': 'Set your new password'}
                }, status=status.HTTP_200_OK)
            else:
                status_code = status.HTTP_429_TOO_MANY_REQUESTS if attempts_remaining == 0 else status.HTTP_400_BAD_REQUEST
                return Response({
                    'status': 'error',
                    'message': message,
                    'errors': {'otp': [message]},
                    'attempts_remaining': attempts_remaining
                }, status=status_code)
                
        except Exception as e:
            print(f"PasswordResetVerifyOTP error: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                'status': 'error',
                'message': 'OTP verification failed',
                'errors': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Password reset successfully"
            ),
            400: OpenApiResponse(description="Validation error or OTP not verified"),
        },
        tags=['Password Reset'],
        summary="Confirm password reset",
        description="Sets new password after OTP verification"
    )
    def post(self, request):
        try:
            serializer = PasswordResetConfirmSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                user = serializer.validated_data['user']
                new_password = serializer.validated_data['new_password']
                
                user.set_password(new_password)
                user.clear_otp()
                user.save()
                
                return Response({
                    'status': 'success',
                    'message': 'Password has been reset successfully. You can now login with your new password.',
                    'data': {'email': user.email}
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            print(f"PasswordResetConfirm error: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                'status': 'error',
                'message': 'Password reset failed',
                'errors': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)