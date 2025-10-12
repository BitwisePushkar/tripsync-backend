from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from account.serializers import UserRegistrationSerializer, UserLoginSerializer, UserProfileSerializer
from account.models import User
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from account.pagination import StandardResultsSetPagination, LargeResultsSetPagination, CustomLimitOffsetPagination
from django.db import models

def get_tokens_for_user(user):
    if not user.is_active:
        raise AuthenticationFailed("User account is deactivated. Please contact support.")
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
                return Response({
                    'status': 'success',
                    'message': 'Registration successful! Please verify your email.',
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
            404: OpenApiResponse(description="User not found"),
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


class UserListView(ListAPIView):
    queryset = User.objects.all().order_by('-created_at')
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = StandardResultsSetPagination
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='page',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Page number',
                required=False
            ),
            OpenApiParameter(
                name='page_size',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Number of results per page (max 100)',
                required=False
            ),
            OpenApiParameter(
                name='search',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Search by name or email',
                required=False
            ),
            OpenApiParameter(
                name='is_verified',
                type=bool,
                location=OpenApiParameter.QUERY,
                description='Filter by email verification status',
                required=False
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=UserProfileSerializer(many=True),
                description="List of users with pagination",
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={
                            'status': 'success',
                            'count': 50,
                            'total_pages': 5,
                            'current_page': 1,
                            'page_size': 10,
                            'next': 'http://api.example.com/users/?page=2',
                            'previous': None,
                            'results': [
                                {
                                    'id': 1,
                                    'email': 'user1@example.com',
                                    'name': 'John Doe',
                                    'phone_number': '+919876543210',
                                    'is_email_verified': True,
                                    'created_at': '2024-01-15T10:30:00Z'
                                }
                            ]
                        }
                    )
                ]
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
            queryset = queryset.filter(
                models.Q(name__icontains=search) | 
                models.Q(email__icontains=search)
            )
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
                description="User profile retrieved successfully",
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={
                            'status': 'success',
                            'data': {
                                'id': 1,
                                'email': 'user@example.com',
                                'name': 'John Doe',
                                'phone_number': '+919876543210',
                                'is_email_verified': True,
                                'created_at': '2024-01-15T10:30:00Z'
                            }
                        }
                    )
                ]
            ),
            401: OpenApiResponse(description="Unauthorized - Token required"),
        },
        tags=['User Management'],
        summary="Get current user profile",
        description="Retrieve the profile of the currently authenticated user"
    )
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response({
            'status': 'success',
            'data': serializer.data
        }, status=status.HTTP_200_OK)