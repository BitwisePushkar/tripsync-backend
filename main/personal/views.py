from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from rest_framework_simplejwt.exceptions import TokenError
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse, inline_serializer
from drf_spectacular.types import OpenApiTypes
from .models import Profile
from .serializers import (UserListSerializer,UserProfileSearchSerializer,UserProfilePublicSerializer,ProfileCreateSerializer,
                          ProfileUpdateSerializer,ProfileSerializer,EmergencySOSSerializer,)
from .utils import SMSService
import logging
from django.utils import timezone
from django.conf import settings
from account.models import User  

logger = logging.getLogger(__name__)
OTP_EXPIRY_MINUTES = getattr(settings, 'OTP_EXPIRY_MINUTES',  5)
MAX_OTP_ATTEMPTS = getattr(settings, 'MAX_OTP_ATTEMPTS',    3)
OTP_LOCKOUT_MINUTES = getattr(settings, 'OTP_LOCKOUT_MINUTES', 15)

@extend_schema(tags=['Profile'])
class ProfileDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    @extend_schema(
        summary="Create Profile & Send Phone OTP",
        description=(
            "Creates the authenticated user's profile and sends a 6-digit OTP "
        ),
        request={
            'multipart/form-data': {
                'type': 'object',
                'required': ['fname', 'lname', 'phone_number', 'date', 'gender',
                             'bio', 'bgroup', 'ename', 'enumber', 'erelation', 'prefrence'],
                'properties': {
                    'fname':        {'type': 'string', 'example': 'John'},
                    'lname':        {'type': 'string', 'example': 'Doe'},
                    'phone_number': {'type': 'string', 'example': '+911234567890'},
                    'date':         {'type': 'string', 'format': 'date', 'example': '1998-05-15'},
                    'gender':       {'type': 'string', 'enum': ['male', 'female', 'other']},
                    'bio':          {'type': 'string', 'example': 'Loves hiking and travel'},
                    'profile_pic':  {'type': 'string', 'format': 'binary', 'description': 'Optional · max 5MB · jpg/jpeg/png/webp'},
                    'bgroup':       {'type': 'string', 'enum': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']},
                    'allergies':    {'type': 'string', 'example': 'Peanuts, Dust'},
                    'medical':      {'type': 'string', 'example': 'Asthma, takes inhaler'},
                    'ename':        {'type': 'string', 'example': 'Jane Doe'},
                    'enumber':      {'type': 'string', 'example': '+911987654321'},
                    'erelation':    {'type': 'string', 'enum': ['Spouse', 'Parent', 'Friend', 'Sibling']},
                    'prefrence':    {'type': 'string', 'enum': ['Adventure', 'Relaxation', 'Nature', 'Explore', 'Spiritual', 'Historic']},
                }
            }
        },
        responses={
            201: OpenApiResponse(
                description="Profile created, OTP sent via SMS",
                examples=[
                    OpenApiExample(
                        name="Success",
                        value={
                            "success": True,
                            "message": "Profile created successfully. OTP sent for verification.",
                            "data": {
                                "phone_number": "+911234567890",
                                "otp_expiry_minutes": 5,
                                "max_attempts": 3,
                                "profile_pic_uploaded": True
                            }
                        },
                        response_only=True,
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Profile already exists or validation failed",
                examples=[
                    OpenApiExample(
                        name="Error — Profile Already Exists",
                        value={
                            "success": False,
                            "message": "Profile already exists",
                            "error_code": "PROFILE_EXISTS"
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name="Error — Validation Failed",
                        value={
                            "success": False,
                            "message": "Validation failed",
                            "errors": {
                                "phone_number": ["Phone number must be in international format (e.g., +1234567890)"],
                                "enumber": ["Emergency contact number cannot be the same as your phone number"]
                            }
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name="Error — Age Validation",
                        value={
                            "success": False,
                            "message": "Validation failed",
                            "errors": {
                                "date": ["You must be at least 13 years old to create an account"]
                            }
                        },
                        response_only=True,
                    ),
                ]
            ),
            503: OpenApiResponse(
                description="SMS sending failed",
                examples=[
                    OpenApiExample(
                        name="Error — SMS Failed",
                        value={
                            "success": False,
                            "message": "Failed to send OTP: SMS service timeout",
                            "error_code": "SMS_FAILED"
                        },
                        response_only=True,
                    )
                ]
            ),
        }
    )
    def post(self, request):
        try:
            if hasattr(request.user, 'profile'):
                return Response({'success': False, 'message': 'Profile already exists', 'error_code': 'PROFILE_EXISTS'},status=status.HTTP_400_BAD_REQUEST)
            serializer = ProfileCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({'success': False, 'message': 'Validation failed', 'errors': serializer.errors},status=status.HTTP_400_BAD_REQUEST)
            validated_data = serializer.validated_data
            phone_number = validated_data['phone_number']
            profile_pic = request.FILES.get('profile_pic')
            profile = Profile.objects.create(
                user=request.user,
                is_phone_verified=False,
                fname=validated_data['fname'],
                lname=validated_data['lname'],
                phone_number=phone_number,
                date=validated_data.get('date'),
                gender=validated_data.get('gender', ''),
                bio=validated_data.get('bio', ''),
                bgroup=validated_data.get('bgroup', ''),
                allergies=validated_data.get('allergies', ''),
                medical=validated_data.get('medical', ''),
                ename=validated_data.get('ename', ''),
                enumber=validated_data.get('enumber', ''),
                erelation=validated_data.get('erelation', ''),
                prefrence=validated_data.get('prefrence', ''),
            )
            profile_pic_uploaded = False
            if profile_pic:
                profile.profile_pic = profile_pic
                profile.save()
                profile_pic_uploaded = True
            otp_code = profile.generate_otp()
            sms_service = SMSService()
            sms_success, sms_message = sms_service.send_otp(phone_number, otp_code)
            if not sms_success:
                profile.delete()
                return Response({'success': False, 'message': f'Failed to send OTP: {sms_message}', 'error_code': 'SMS_FAILED'},status=status.HTTP_503_SERVICE_UNAVAILABLE)
            logger.info(f"Profile created and OTP sent to {phone_number} for user {request.user.id}")
            return Response({'success': True,'message': 'Profile created successfully. OTP sent for verification.',
                             'data': {'phone_number': phone_number,'otp_expiry_minutes': OTP_EXPIRY_MINUTES,'max_attempts': MAX_OTP_ATTEMPTS,
                                      'profile_pic_uploaded': profile_pic_uploaded}},status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error in ProfileDetailView POST: {str(e)}")
            return Response({'success': False, 'message': 'An error occurred. Please try again later.', 'error_code': 'INTERNAL_ERROR'},status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @extend_schema(
        summary="Get My Profile",
        description="Returns the authenticated user's complete profile.",
        responses={
            200: OpenApiResponse(
                description="Profile retrieved",
                examples=[
                    OpenApiExample(
                        name="Success",
                        value={
                            "success": True,
                            "data": {
                                "profile": {
                                    "id": 1,
                                    "email": "user@example.com",
                                    "fname": "John",
                                    "lname": "Doe",
                                    "phone_number": "+911234567890",
                                    "is_phone_verified": True,
                                    "date": "1998-05-15",
                                    "gender": "male",
                                    "bio": "Loves hiking and travel",
                                    "profile_pic": None,
                                    "profile_pic_url": "https://s3.amazonaws.com/bucket/profile_pics/pic.jpg",
                                    "bgroup": "O+",
                                    "allergies": "Peanuts",
                                    "medical": "Asthma",
                                    "ename": "Jane Doe",
                                    "enumber": "+911987654321",
                                    "erelation": "Spouse",
                                    "prefrence": "Adventure",
                                    "created_at": "2024-01-15T10:30:00Z",
                                    "updated_at": "2024-01-15T10:30:00Z"
                                }
                            }
                        },
                        response_only=True,
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Profile not found",
                examples=[
                    OpenApiExample(
                        name="Error — No Profile",
                        value={
                            "success": False,
                            "message": "Profile not found",
                            "error_code": "PROFILE_NOT_FOUND"
                        },
                        response_only=True,
                    )
                ]
            ),
        }
    )
    def get(self, request):
        try:
            profile = request.user.profile
            serializer = ProfileSerializer(profile, context={'request': request})
            return Response({'success': True, 'data': {'profile': serializer.data}}, status=status.HTTP_200_OK)
        except Profile.DoesNotExist:
            return Response({'success': False, 'message': 'Profile not found', 'error_code': 'PROFILE_NOT_FOUND'},status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        summary="Update Profile",
        description=(
            "Partially updates profile fields. Phone verification required.\n\n"
        ),
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'fname':       {'type': 'string', 'example': 'John'},
                    'lname':       {'type': 'string', 'example': 'Doe'},
                    'date':        {'type': 'string', 'format': 'date', 'example': '1998-05-15'},
                    'gender':      {'type': 'string', 'enum': ['male', 'female', 'other']},
                    'bio':         {'type': 'string', 'example': 'Updated bio'},
                    'profile_pic': {'type': 'string', 'format': 'binary', 'description': 'max 5MB · jpg/jpeg/png/webp'},
                    'bgroup':      {'type': 'string', 'enum': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']},
                    'allergies':   {'type': 'string', 'example': 'Peanuts, Dust'},
                    'medical':     {'type': 'string', 'example': 'Asthma'},
                    'ename':       {'type': 'string', 'example': 'Jane Doe'},
                    'enumber':     {'type': 'string', 'example': '+911987654321'},
                    'erelation':   {'type': 'string', 'enum': ['Spouse', 'Parent', 'Friend', 'Sibling']},
                    'prefrence':   {'type': 'string', 'enum': ['Adventure', 'Relaxation', 'Nature', 'Explore', 'Spiritual', 'Historic']},
                }
            }
        },
        responses={
            200: OpenApiResponse(
                description="Profile updated",
                examples=[
                    OpenApiExample(
                        name="Success",
                        value={
                            "success": True,
                            "message": "Profile updated successfully",
                            "data": {"profile": {"fname": "John", "lname": "Doe", "bio": "Updated bio"}}
                        },
                        response_only=True,
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Validation failed",
                examples=[
                    OpenApiExample(
                        name="Error — Validation",
                        value={
                            "success": False,
                            "message": "Validation failed",
                            "errors": {"enumber": ["Emergency contact number cannot be the same as your phone number"]}
                        },
                        response_only=True,
                    )
                ]
            ),
            403: OpenApiResponse(
                description="Phone not verified",
                examples=[
                    OpenApiExample(
                        name="Error — Phone Not Verified",
                        value={
                            "success": False,
                            "message": "Please verify your phone number first",
                            "error_code": "PHONE_NOT_VERIFIED"
                        },
                        response_only=True,
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Profile not found",
                examples=[
                    OpenApiExample(
                        name="Error — No Profile",
                        value={
                            "success": False,
                            "message": "Profile not found",
                            "error_code": "PROFILE_NOT_FOUND"
                        },
                        response_only=True,
                    )
                ]
            ),
        }
    )
    def patch(self, request):
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return Response({'success': False, 'message': 'Profile not found', 'error_code': 'PROFILE_NOT_FOUND'},status=status.HTTP_404_NOT_FOUND)
        if not profile.is_phone_verified:
            return Response({'success': False, 'message': 'Please verify your phone number first', 'error_code': 'PHONE_NOT_VERIFIED'},status=status.HTTP_403_FORBIDDEN)
        serializer = ProfileUpdateSerializer(profile, data=request.data, partial=True, context={'request': request})
        if not serializer.is_valid():
            return Response({'success': False, 'message': 'Validation failed', 'errors': serializer.errors},status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        profile_serializer = ProfileSerializer(profile, context={'request': request})
        return Response({'success': True, 'message': 'Profile updated successfully', 'data': {'profile': profile_serializer.data}},status=status.HTTP_200_OK)

    @extend_schema(
        summary="Delete Profile & Account",
        description=(
            "Permanently deletes the user's profile and the associated user account. "
        ),
        responses={
            200: OpenApiResponse(
                description="Deleted successfully",
                examples=[
                    OpenApiExample(
                        name="Success",
                        value={"success": True, "message": "Profile and user account deleted successfully"},
                        response_only=True,
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Profile not found",
                examples=[
                    OpenApiExample(
                        name="Error",
                        value={"success": False, "message": "Profile not found", "error_code": "PROFILE_NOT_FOUND"},
                        response_only=True,
                    )
                ]
            ),
            500: OpenApiResponse(
                description="Internal error",
                examples=[
                    OpenApiExample(
                        name="Error",
                        value={"success": False, "message": "An error occurred.", "error_code": "INTERNAL_ERROR"},
                        response_only=True,
                    )
                ]
            ),
        }
    )
    def delete(self, request):
        try:
            try:
                request.user.profile
            except Profile.DoesNotExist:
                return Response({'success': False, 'message': 'Profile not found', 'error_code': 'PROFILE_NOT_FOUND'},status=status.HTTP_404_NOT_FOUND)
            user_id = request.user.id
            user_email = request.user.email
            request.user.delete()  
            logger.info(f"User {user_id} ({user_email}) and profile deleted")
            return Response({'success': True, 'message': 'Profile and user account deleted successfully'},status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in ProfileDetailView DELETE: {str(e)}")
            return Response({'success': False, 'message': 'An error occurred. Please try again later.', 'error_code': 'INTERNAL_ERROR'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VerifyOTPView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    @extend_schema(
        tags=['Profile'],
        summary="Verify Phone OTP",
        description=(
            "Verifies the 6-digit OTP sent to the registered phone number.\n\n"
        ),
        request=inline_serializer(
            name="VerifyOTPRequest",
            fields={"otp_code": OpenApiTypes.STR}
        ),
        responses={
            200: OpenApiResponse(
                description="Phone verified successfully",
                examples=[
                    OpenApiExample(
                        name="Success",
                        value={
                            "success": True,
                            "message": "Phone number verified successfully!",
                            "data": {
                                "profile": {
                                    "id": 1,
                                    "email": "user@example.com",
                                    "fname": "John",
                                    "lname": "Doe",
                                    "phone_number": "+911234567890",
                                    "is_phone_verified": True,
                                }
                            }
                        },
                        response_only=True,
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Wrong OTP, expired, or already verified",
                examples=[
                    OpenApiExample(
                        name="Error — Wrong OTP",
                        value={
                            "success": False,
                            "message": "Invalid OTP. 2 attempt(s) remaining.",
                            "data": {"attempts_remaining": 2},
                            "error_code": "OTP_VERIFICATION_FAILED"
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name="Error — OTP Expired",
                        value={
                            "success": False,
                            "message": "OTP has expired. Please request a new one.",
                            "data": {"attempts_remaining": 0},
                            "error_code": "OTP_VERIFICATION_FAILED"
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name="Error — Already Verified",
                        value={
                            "success": False,
                            "message": "Phone number already verified.",
                            "error_code": "ALREADY_VERIFIED"
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name="Error — OTP Missing",
                        value={
                            "success": False,
                            "message": "OTP code is required",
                            "errors": {"otp_code": ["This field is required"]},
                            "error_code": "OTP_VERIFICATION_FAILED"
                        },
                        response_only=True,
                    ),
                ]
            ),
            404: OpenApiResponse(
                description="Profile not found",
                examples=[
                    OpenApiExample(
                        name="Error — No Profile",
                        value={
                            "success": False,
                            "message": "Profile not found. Please create your profile first.",
                            "error_code": "PROFILE_NOT_FOUND"
                        },
                        response_only=True,
                    )
                ]
            ),
            429: OpenApiResponse(
                description="Account locked after 3 failed attempts",
                examples=[
                    OpenApiExample(
                        name="Error — Account Locked",
                        value={
                            "success": False,
                            "message": "Too many failed attempts. Account locked for 15 minutes.",
                            "data": {"attempts_remaining": 0},
                            "error_code": "OTP_VERIFICATION_FAILED"
                        },
                        response_only=True,
                    )
                ]
            ),
        }
    )
    def post(self, request):
        try:
            try:
                profile = request.user.profile
            except Profile.DoesNotExist:
                return Response({'success': False, 'message': 'Profile not found. Please create your profile first.', 'error_code': 'PROFILE_NOT_FOUND'},status=status.HTTP_404_NOT_FOUND)
            if profile.is_phone_verified:
                return Response({'success': False, 'message': 'Phone number already verified.', 'error_code': 'ALREADY_VERIFIED'},status=status.HTTP_400_BAD_REQUEST)
            otp_code = request.data.get('otp_code', '').strip()
            if not otp_code:
                return Response({'success': False, 'message': 'OTP code is required', 'errors': {'otp_code': ['This field is required']}, 'error_code': 'OTP_VERIFICATION_FAILED'},status=status.HTTP_400_BAD_REQUEST)
            success, message, attempts_remaining = profile.verify_otp(otp_code)
            if not success:
                resp_status = status.HTTP_429_TOO_MANY_REQUESTS if attempts_remaining == 0 else status.HTTP_400_BAD_REQUEST
                return Response({'success': False, 'message': message, 'data': {'attempts_remaining': attempts_remaining}, 'error_code': 'OTP_VERIFICATION_FAILED'},status=resp_status)
            sms_service = SMSService()
            sms_service.send_verification_success(profile.phone_number, profile.fname)
            logger.info(f"Phone verified for user {request.user.id}")
            profile_serializer = ProfileSerializer(profile, context={'request': request})
            return Response({'success': True, 'message': 'Phone number verified successfully!', 'data': {'profile': profile_serializer.data}},status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in VerifyOTPView: {str(e)}")
            return Response({'success': False, 'message': 'An error occurred. Please try again later.', 'error_code': 'INTERNAL_ERROR'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ResendOTPView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    @extend_schema(
        tags=['Profile'],
        summary="Resend Phone OTP",
        description=(
            "Resends a fresh OTP to the user's registered phone number.\n\n"
        ),
        request=None,
        responses={
            200: OpenApiResponse(
                description="OTP resent successfully",
                examples=[
                    OpenApiExample(
                        name="Success",
                        value={
                            "success": True,
                            "message": "OTP resent successfully",
                            "data": {"otp_expiry_minutes": 5, "max_attempts": 3}
                        },
                        response_only=True,
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Phone already verified",
                examples=[
                    OpenApiExample(
                        name="Error — Already Verified",
                        value={
                            "success": False,
                            "message": "Phone number already verified.",
                            "error_code": "ALREADY_VERIFIED"
                        },
                        response_only=True,
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Profile not found",
                examples=[
                    OpenApiExample(
                        name="Error — No Profile",
                        value={
                            "success": False,
                            "message": "Profile not found.",
                            "error_code": "PROFILE_NOT_FOUND"
                        },
                        response_only=True,
                    )
                ]
            ),
            429: OpenApiResponse(
                description="Account locked or cooldown active",
                examples=[
                    OpenApiExample(
                        name="Error — Account Locked",
                        value={
                            "success": False,
                            "message": "Too many attempts. Please try again later.",
                            "error_code": "OTP_LOCKED"
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name="Error — Resend Cooldown",
                        value={
                            "success": False,
                            "message": "Please wait 85 seconds before requesting another OTP.",
                            "error_code": "OTP_COOLDOWN_ACTIVE"
                        },
                        response_only=True,
                    ),
                ]
            ),
            500: OpenApiResponse(
                description="SMS delivery failed",
                examples=[
                    OpenApiExample(
                        name="Error — SMS Failed",
                        value={
                            "success": False,
                            "message": "Failed to send OTP: SMS service timeout",
                            "error_code": "SMS_FAILED"
                        },
                        response_only=True,
                    )
                ]
            ),
        }
    )
    def post(self, request):
        try:
            try:
                profile = request.user.profile
            except Profile.DoesNotExist:
                return Response({'success': False, 'message': 'Profile not found.', 'error_code': 'PROFILE_NOT_FOUND'},status=status.HTTP_404_NOT_FOUND)
            if profile.is_phone_verified:
                return Response({'success': False, 'message': 'Phone number already verified.', 'error_code': 'ALREADY_VERIFIED'},status=status.HTTP_400_BAD_REQUEST)
            if profile.is_otp_locked():
                return Response({'success': False, 'message': 'Too many attempts. Please try again later.', 'error_code': 'OTP_LOCKED'},status=status.HTTP_429_TOO_MANY_REQUESTS)
            if profile.last_otp_sent_at:
                time_since_last = (timezone.now() - profile.last_otp_sent_at).total_seconds()
                if time_since_last < 120:
                    remaining = int(120 - time_since_last)
                    return Response({'success': False, 'message': f'Please wait {remaining} seconds before requesting another OTP.', 'error_code': 'OTP_COOLDOWN_ACTIVE'},status=status.HTTP_429_TOO_MANY_REQUESTS)
            otp_code = profile.generate_otp()
            sms_service = SMSService()
            sms_success, sms_message = sms_service.send_otp(profile.phone_number, otp_code)
            if not sms_success:
                return Response({'success': False, 'message': f'Failed to send OTP: {sms_message}', 'error_code': 'SMS_FAILED'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            logger.info(f"OTP resent to {profile.phone_number} for user {request.user.id}")
            return Response({'success': True, 'message': 'OTP resent successfully', 'data': {'otp_expiry_minutes': OTP_EXPIRY_MINUTES, 'max_attempts': MAX_OTP_ATTEMPTS}},status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in ResendOTPView: {str(e)}")
            return Response({'success': False, 'message': 'An error occurred. Please try again later.', 'error_code': 'INTERNAL_ERROR'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(tags=['Emergency'])
class EmergencySOSView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    @extend_schema(
        summary="Send Emergency SOS",
        description=(
            "Sends an emergency alert SMS to the registered emergency contact.\n\n"
        ),
        request=EmergencySOSSerializer,
        responses={
            200: OpenApiResponse(
                description="Emergency alert sent",
                examples=[
                    OpenApiExample(
                        name="Success",
                        value={
                            "success": True,
                            "message": "Emergency alert sent successfully",
                            "data": {
                                "sent_to": "+911987654321",
                                "contact_name": "Jane Doe",
                                "relation": "Spouse"
                            }
                        },
                        response_only=True,
                    )
                ]
            ),
            400: OpenApiResponse(
                description="No emergency contact or validation error",
                examples=[
                    OpenApiExample(
                        name="Error — No Emergency Contact",
                        value={
                            "success": False,
                            "message": "No emergency contact configured. Please add emergency contact in your profile.",
                            "error_code": "NO_EMERGENCY_CONTACT"
                        },
                        response_only=True,
                    )
                ]
            ),
            403: OpenApiResponse(
                description="Phone not verified",
                examples=[
                    OpenApiExample(
                        name="Error — Phone Not Verified",
                        value={
                            "success": False,
                            "message": "Please verify your phone number first",
                            "error_code": "PHONE_NOT_VERIFIED"
                        },
                        response_only=True,
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Profile not found",
                examples=[
                    OpenApiExample(
                        name="Error — No Profile",
                        value={
                            "success": False,
                            "message": "Profile not found. Please create your profile first.",
                            "error_code": "PROFILE_NOT_FOUND"
                        },
                        response_only=True,
                    )
                ]
            ),
            500: OpenApiResponse(
                description="SMS delivery failed",
                examples=[
                    OpenApiExample(
                        name="Error — SMS Failed",
                        value={
                            "success": False,
                            "message": "Failed to send emergency alert: SMS service error",
                            "error_code": "SMS_FAILED"
                        },
                        response_only=True,
                    )
                ]
            ),
        },
        examples=[
            OpenApiExample(
                name="With Custom Message & Location",
                value={"message": "I need help! Please check on me.", "location": "Near Central Park, New York"},
                request_only=True,
            ),
            OpenApiExample(
                name="Empty Body (default alert)",
                value={},
                request_only=True,
            ),
        ]
    )
    def post(self, request):
        try:
            try:
                profile = request.user.profile
            except Profile.DoesNotExist:
                return Response({'success': False, 'message': 'Profile not found. Please create your profile first.', 'error_code': 'PROFILE_NOT_FOUND'},status=status.HTTP_404_NOT_FOUND)
            if not profile.is_phone_verified:
                return Response({'success': False, 'message': 'Please verify your phone number first', 'error_code': 'PHONE_NOT_VERIFIED'},status=status.HTTP_403_FORBIDDEN)
            if not profile.enumber or not profile.ename:
                return Response({'success': False, 'message': 'No emergency contact configured. Please add emergency contact in your profile.', 'error_code': 'NO_EMERGENCY_CONTACT'},status=status.HTTP_400_BAD_REQUEST)
            serializer = EmergencySOSSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({'success': False, 'message': 'Validation failed', 'errors': serializer.errors},status=status.HTTP_400_BAD_REQUEST)
            custom_message = serializer.validated_data.get('message', '')
            location = serializer.validated_data.get('location', '')
            sms_service = SMSService()
            sms_success, sms_message = sms_service.send_emergency_alert(
                emergency_number=profile.enumber,
                user_name=f"{profile.fname} {profile.lname}",
                user_phone=profile.phone_number,
                custom_message=custom_message,
                location=location
            )
            if not sms_success:
                return Response({'success': False, 'message': f'Failed to send emergency alert: {sms_message}', 'error_code': 'SMS_FAILED'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            logger.info(f"Emergency SOS sent from user {request.user.id} to {profile.enumber}")
            return Response({'success': True,'message': 'Emergency alert sent successfully',
                             'data': {'sent_to': profile.enumber,'contact_name': profile.ename,'relation': profile.erelation or 'Not specified'}},
                             status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in EmergencySOSView: {str(e)}")
            return Response({'success': False, 'message': 'An error occurred. Please try again later.', 'error_code': 'INTERNAL_ERROR'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserListView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    @extend_schema(
        tags=['Profile'],
        summary="List All Verified Users",
        description=(
            "Returns a list of all users who have completed phone verification.\n\n"
        ),
        responses={
            200: OpenApiResponse(
                description="Verified users list",
                examples=[
                    OpenApiExample(
                        name="Success",
                        value={
                            "success": True,
                            "message": "Users retrieved successfully",
                            "data": {
                                "users": [
                                    {"id": 1, "fname": "John", "lname": "Doe"},
                                    {"id": 2, "fname": "Jane", "lname": "Smith"}
                                ],
                                "count": 2
                            }
                        },
                        response_only=True,
                    )
                ]
            ),
            403: OpenApiResponse(
                description="Caller's phone not verified",
                examples=[
                    OpenApiExample(
                        name="Error — Not Verified",
                        value={"success": False, "message": "Please verify your phone number first", "error_code": "PHONE_NOT_VERIFIED"},
                        response_only=True,
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Caller has no profile",
                examples=[
                    OpenApiExample(
                        name="Error — No Profile",
                        value={"success": False, "message": "Profile not found. Please create your profile first.", "error_code": "PROFILE_NOT_FOUND"},
                        response_only=True,
                    )
                ]
            ),
        }
    )
    def get(self, request):
        try:
            try:
                profile = request.user.profile
                if not profile.is_phone_verified:
                    return Response({'success': False, 'message': 'Please verify your phone number first', 'error_code': 'PHONE_NOT_VERIFIED'},status=status.HTTP_403_FORBIDDEN)
            except Profile.DoesNotExist:
                return Response({'success': False, 'message': 'Profile not found. Please create your profile first.', 'error_code': 'PROFILE_NOT_FOUND'},status=status.HTTP_404_NOT_FOUND)
            verified_users = Profile.objects.filter(is_phone_verified=True).select_related('user').order_by('fname', 'lname')
            serializer = UserListSerializer(verified_users, many=True)
            return Response({'success': True,'message': 'Users retrieved successfully','data': {'users': serializer.data, 'count': verified_users.count()}},
                            status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in UserListView: {str(e)}")
            return Response({'success': False, 'message': 'An error occurred. Please try again later.', 'error_code': 'INTERNAL_ERROR'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserProfileByNameView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    @extend_schema(
        tags=['Profile'],
        summary="Search Users by Name",
        description=(
            "Searches verified users by first and last name (case-insensitive).\n\n"
        ),
        request=UserProfileSearchSerializer,
        responses={
            200: OpenApiResponse(
                description="Search results",
                examples=[
                    OpenApiExample(
                        name="Single Result",
                        value={
                            "success": True,
                            "message": "1 user found with the provided name",
                            "data": {
                                "count": 1,
                                "users": [
                                    {
                                        "id": 1,
                                        "fname": "John",
                                        "lname": "Doe",
                                        "bio": "Loves hiking",
                                        "gender": "male",
                                        "prefrence": "Adventure",
                                        "profile_pic_url": "https://s3.amazonaws.com/bucket/profile_pics/pic.jpg"
                                    }
                                ]
                            }
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name="Multiple Results",
                        value={
                            "success": True,
                            "message": "2 users found with the provided name",
                            "data": {
                                "count": 2,
                                "users": [
                                    {"id": 1, "fname": "John", "lname": "Doe", "bio": "Hiker", "gender": "male", "prefrence": "Adventure", "profile_pic_url": None},
                                    {"id": 5, "fname": "John", "lname": "Doe", "bio": "Traveller", "gender": "male", "prefrence": "Nature", "profile_pic_url": None}
                                ]
                            }
                        },
                        response_only=True,
                    ),
                ]
            ),
            400: OpenApiResponse(
                description="Missing search fields",
                examples=[
                    OpenApiExample(
                        name="Error — Missing Fields",
                        value={"success": False, "message": "Validation failed", "errors": {"fname": ["This field is required."]}},
                        response_only=True,
                    )
                ]
            ),
            403: OpenApiResponse(
                description="Caller's phone not verified",
                examples=[
                    OpenApiExample(
                        name="Error — Not Verified",
                        value={"success": False, "message": "Please verify your phone number", "error_code": "PHONE_NOT_VERIFIED"},
                        response_only=True,
                    )
                ]
            ),
            404: OpenApiResponse(
                description="No matching users found",
                examples=[
                    OpenApiExample(
                        name="Error — Not Found",
                        value={"success": False, "message": "No verified user found", "error_code": "USER_NOT_FOUND"},
                        response_only=True,
                    )
                ]
            ),
        },
        examples=[
            OpenApiExample(
                name="Search Request",
                value={"fname": "John", "lname": "Doe"},
                request_only=True,
            )
        ]
    )
    def post(self, request):
        try:
            try:
                profile = request.user.profile
                if not profile.is_phone_verified:
                    return Response({'success': False, 'message': 'Please verify your phone number', 'error_code': 'PHONE_NOT_VERIFIED'},status=status.HTTP_403_FORBIDDEN)
            except Profile.DoesNotExist:
                return Response({'success': False, 'message': 'Profile not found.', 'error_code': 'PROFILE_NOT_FOUND'},status=status.HTTP_404_NOT_FOUND)
            serializer = UserProfileSearchSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({'success': False, 'message': 'Validation failed', 'errors': serializer.errors},status=status.HTTP_400_BAD_REQUEST)
            fname = serializer.validated_data['fname'].strip()
            lname = serializer.validated_data['lname'].strip()
            user_profiles = Profile.objects.select_related('user').filter(fname__iexact=fname,lname__iexact=lname,
                                                                          is_phone_verified=True).order_by('id')
            if not user_profiles.exists():
                return Response({'success': False, 'message': 'No verified user found', 'error_code': 'USER_NOT_FOUND'},status=status.HTTP_404_NOT_FOUND)
            profile_serializer = UserProfilePublicSerializer(user_profiles, many=True, context={'request': request})
            user_count = user_profiles.count()
            message = f"{user_count} user{'s' if user_count > 1 else ''} found with the provided name"
            logger.info(f"User {request.user.id} searched for {fname} {lname} — {user_count} result(s)")
            return Response({'success': True, 'message': message, 'data': {'count': user_count, 'users': profile_serializer.data}},status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in UserProfileByNameView: {str(e)}")
            return Response({'success': False, 'message': 'An error occurred.', 'error_code': 'INTERNAL_ERROR'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(tags=['Profile'])
class AccountDeactivateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    @extend_schema(
        summary="Deactivate Account",
        description=(
            "Deactivates your account immediately.\n\n"
        ),
        request={
            'application/json': {
                'type': 'object',
                'required': ['password'],
                'properties': {
                    'password': {
                        'type': 'string',
                        'example': 'MySecurePass123!',
                        'description': 'Your current account password — required for confirmation'
                    }
                }
            }
        },
        responses={
            200: OpenApiResponse(
                description="Account deactivated",
                examples=[
                    OpenApiExample(
                        name="Success",
                        value={
                            "success": True,
                            "message": "Account deactivated successfully. All sessions have been terminated.",
                            "data": {
                                "sessions_terminated": 3,
                                "is_active": False
                            }
                        },
                        response_only=True,
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Wrong password or already deactivated",
                examples=[
                    OpenApiExample(
                        name="Error — Wrong Password",
                        value={
                            "success": False,
                            "message": "Incorrect password",
                            "error_code": "INVALID_PASSWORD"
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name="Error — Already Deactivated",
                        value={
                            "success": False,
                            "message": "Account is already deactivated",
                            "error_code": "ALREADY_DEACTIVATED"
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name="Error — Missing Password",
                        value={
                            "success": False,
                            "message": "Password is required",
                            "error_code": "PASSWORD_REQUIRED"
                        },
                        response_only=True,
                    ),
                ]
            ),
            404: OpenApiResponse(
                description="Profile not found",
                examples=[
                    OpenApiExample(
                        name="Error",
                        value={
                            "success": False,
                            "message": "Profile not found",
                            "error_code": "PROFILE_NOT_FOUND"
                        },
                        response_only=True,
                    )
                ]
            ),
        }
    )
    def post(self, request):
        try:
            try:
                request.user.profile
            except Profile.DoesNotExist:
                return Response({'success': False, 'message': 'Profile not found', 'error_code': 'PROFILE_NOT_FOUND'},status=status.HTTP_404_NOT_FOUND)
            if not request.user.is_active:
                return Response({'success': False, 'message': 'Account is already deactivated', 'error_code': 'ALREADY_DEACTIVATED'},status=status.HTTP_400_BAD_REQUEST)
            password = request.data.get('password', '').strip()
            if not password:
                return Response({'success': False, 'message': 'Password is required', 'error_code': 'PASSWORD_REQUIRED'},status=status.HTTP_400_BAD_REQUEST)
            if not request.user.check_password(password):
                return Response({'success': False, 'message': 'Incorrect password', 'error_code': 'INVALID_PASSWORD'},status=status.HTTP_400_BAD_REQUEST)
            outstanding_tokens = OutstandingToken.objects.filter(user=request.user)
            blacklisted_count = 0
            for token in outstanding_tokens:
                if not BlacklistedToken.objects.filter(token=token).exists():
                    BlacklistedToken.objects.create(token=token)
                    blacklisted_count += 1
            request.user.is_active = False
            request.user.save(update_fields=['is_active', 'updated_at'])
            logger.info(f"Account deactivated: user {request.user.id} ({request.user.email}) — "f"{blacklisted_count} token(s) blacklisted")
            return Response({'success': True,'message': 'Account deactivated successfully. All sessions have been terminated.',
                             'data': {'sessions_terminated': blacklisted_count,'is_active': False}},status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in AccountDeactivateView: {str(e)}")
            return Response({'success': False, 'message': 'An error occurred. Please try again later.', 'error_code': 'INTERNAL_ERROR'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(tags=['Profile'])
class AccountReactivateView(APIView):
    permission_classes = [] 
    parser_classes = [JSONParser]
    @extend_schema(
        summary="Reactivate Account",
        description=(
            "Reactivates a previously deactivated account.\n\n"
        ),
        request={
            'application/json': {
                'type': 'object',
                'required': ['email', 'password'],
                'properties': {
                    'email': {
                        'type': 'string',
                        'format': 'email',
                        'example': 'user@example.com'
                    },
                    'password': {
                        'type': 'string',
                        'example': 'MySecurePass123!'
                    }
                }
            }
        },
        responses={
            200: OpenApiResponse(
                description="Account reactivated — fresh tokens issued",
                examples=[
                    OpenApiExample(
                        name="Success",
                        value={
                            "success": True,
                            "message": "Account reactivated successfully. Please log in.",
                            "data": {
                                "is_active": True,
                                "access":  "eyJ0eXAiOiJKV1Qi...",
                                "refresh": "eyJ0eXAiOiJKV1Qi..."
                            }
                        },
                        response_only=True,
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Missing fields, wrong credentials, or already active",
                examples=[
                    OpenApiExample(
                        name="Error — Wrong Credentials",
                        value={
                            "success": False,
                            "message": "Invalid email or password",
                            "error_code": "INVALID_CREDENTIALS"
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name="Error — Already Active",
                        value={
                            "success": False,
                            "message": "Account is already active. Please log in normally.",
                            "error_code": "ALREADY_ACTIVE"
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name="Error — Missing Fields",
                        value={
                            "success": False,
                            "message": "Email and password are required",
                            "error_code": "FIELDS_REQUIRED"
                        },
                        response_only=True,
                    ),
                ]
            ),
            404: OpenApiResponse(
                description="No account with that email",
                examples=[
                    OpenApiExample(
                        name="Error — Not Found",
                        value={
                            "success": False,
                            "message": "No account found with this email",
                            "error_code": "USER_NOT_FOUND"
                        },
                        response_only=True,
                    )
                ]
            ),
        }
    )
    def post(self, request):
        try:
            email = request.data.get('email', '').strip().lower()
            password = request.data.get('password', '').strip()
            if not email or not password:
                return Response({'success': False, 'message': 'Email and password are required', 'error_code': 'FIELDS_REQUIRED'},status=status.HTTP_400_BAD_REQUEST)
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({'success': False, 'message': 'No account found with this email', 'error_code': 'USER_NOT_FOUND'},status=status.HTTP_404_NOT_FOUND)
            if not user.check_password(password):
                return Response({'success': False, 'message': 'Invalid email or password', 'error_code': 'INVALID_CREDENTIALS'},status=status.HTTP_400_BAD_REQUEST)
            if user.is_active:
                return Response({'success': False, 'message': 'Account is already active. Please log in normally.', 'error_code': 'ALREADY_ACTIVE'},status=status.HTTP_400_BAD_REQUEST)
            user.is_active = True
            user.save(update_fields=['is_active', 'updated_at'])
            refresh = RefreshToken.for_user(user)
            logger.info(f"Account reactivated: user {user.id} ({user.email})")
            return Response({'success': True,'message': 'Account reactivated successfully. Please log in.',
                             'data': {'is_active': True,'access':  str(refresh.access_token),'refresh': str(refresh),}},status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in AccountReactivateView: {str(e)}")
            return Response({'success': False, 'message': 'An error occurred. Please try again later.', 'error_code': 'INTERNAL_ERROR'},status=status.HTTP_500_INTERNAL_SERVER_ERROR)        