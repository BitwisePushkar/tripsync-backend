from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import (extend_schema, OpenApiParameter,OpenApiExample,OpenApiResponse,inline_serializer)
from drf_spectacular.types import OpenApiTypes
from .models import Profile
from .serializers import (PersonalDetailsInputSerializer,OTPVerificationSerializer,ProfileUpdateSerializer,ResendOTPSerializer,ProfileSerializer)
from .utils import TwilioSMSService
import logging

logger = logging.getLogger(__name__)

@extend_schema(tags=['Profile'])
class PersonalDetailsCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    @extend_schema(
    summary="Create Profile & Send OTP",
    description="Create a new profile with optional photo and send OTP for verification.",
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string', 'example': 'John Doe'},
                'age': {'type': 'integer', 'example': 25},
                'gender': {'type': 'string', 'enum': ['male', 'female', 'other'], 'example': 'male'},
                'location': {'type': 'string', 'example': 'New York, USA'},
                'phone_number': {'type': 'string', 'example': '+1234567890'},
                'bio': {'type': 'string', 'example': 'Software Developer'},
                'profile_pic': {'type': 'string','format': 'binary','description': 'Optional photo (max 5MB, jpg/jpeg/png/webp)'}
            },
            'required': ['name', 'age', 'gender', 'location', 'phone_number']
        }
    },
    responses={
        201: OpenApiResponse(
            description="Profile created, OTP sent",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "success": True,
                        "message": "OTP sent to +1234567890",
                        "data": {
                            "phone_number": "+1234567890",
                            "otp_expiry_minutes": 5,
                            "max_attempts": 3,
                            "profile_pic_uploaded": True
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Invalid data or profile exists",
            examples=[
                OpenApiExample(
                    "Profile Exists",
                    value={
                        "success": False,
                        "message": "Profile already exists.",
                        "error_code": "PROFILE_EXISTS"
                    }
                )
            ]
        ),
        500: OpenApiResponse(
            description="OTP send failed",
            examples=[
                OpenApiExample(
                    "SMS Failed",
                    value={
                        "success": False,
                        "message": "Failed to send OTP.",
                        "error_code": "SMS_FAILED"
                    }
                )
            ]
        ),
    }
)
    def post(self, request):
        try:
            if hasattr(request.user, 'profile'):
                return Response({'success': False,'message': 'Profile already exists','error_code': 'PROFILE_EXISTS'}, status=status.HTTP_400_BAD_REQUEST)            
            serializer = PersonalDetailsInputSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({'success': False,'message': 'Validation failed','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            validated_data = serializer.validated_data
            phone_number = validated_data['phone_number']
            profile_pic = request.FILES.get('profile_pic')
            profile_pic_uploaded = False
            profile = Profile.objects.create(user=request.user,is_phone_verified=False,**validated_data)

            if profile_pic:
                profile.profile_pic = profile_pic
                profile.save()
                profile_pic_uploaded = True
            
            if profile.is_otp_locked():
                profile.delete() 
                return Response({'success': False,'message': 'Too many attempts. Please try again later.','error_code': 'OTP_LOCKED'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            otp_code = profile.generate_otp()
            sms_service = TwilioSMSService()
            sms_success, sms_message = sms_service.send_otp(phone_number, otp_code)
            
            if not sms_success:
                profile.delete() 
                return Response({'success': False,'message': f'Failed to send OTP: {sms_message}','error_code': 'SMS_FAILED'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            logger.info(f"Profile created and OTP sent to {phone_number} for user {request.user.id}")
            return Response({'success': True,'message': 'Profile created. OTP sent to your phone number for verification.','data': {'phone_number': phone_number,'otp_expiry_minutes': 5,'max_attempts': 3,'profile_pic_uploaded': profile_pic_uploaded}}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error in PersonalDetailsCreateView: {str(e)}")
            return Response({'success': False,'message': 'An error occurred. Please try again later.','error_code': 'INTERNAL_ERROR'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(tags=['OTP'])
class VerifyOTPView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    @extend_schema(
    summary="Verify OTP",
    description="Verify the OTP sent to your phone number",
    request=inline_serializer(
        name="VerifyOTPRequest",
        fields={"otp_code": OpenApiTypes.STR}
    ),
    responses={
        200: OpenApiResponse(
            description="OTP verified successfully",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "success": True,
                        "message": "Phone number verified successfully!",
                        "data": {
                            "profile": {
                                "id": 1,
                                "email": "user@example.com",
                                "name": "John Doe",
                                "age": 25,
                                "gender": "male",
                                "location": "New York, USA",
                                "phone_number": "+1234567890",
                                "is_phone_verified": True,
                                "bio": "Software Developer",
                                "profile_pic": "/media/profile_pics/image.jpg",
                                "profile_pic_url": "https://cdn.myapp.com/media/profile_pics/image.jpg"
                            }
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Invalid or expired OTP",
            examples=[
                OpenApiExample(
                    "Invalid OTP",
                    value={
                        "success": False,
                        "message": "Invalid OTP. 2 attempt(s) remaining.",
                        "data": {"attempts_remaining": 2},
                        "error_code": "OTP_VERIFICATION_FAILED"
                    }
                ),
                OpenApiExample(
                    "OTP Expired",
                    value={
                        "success": False,
                        "message": "OTP expired. Please request a new one.",
                        "error_code": "OTP_EXPIRED"
                    }
                )
            ]
        ),
        404: OpenApiResponse(
            description="Profile not found",
            examples=[
                OpenApiExample(
                    "Not Found",
                    value={
                        "success": False,
                        "message": "Profile not found. Please create your profile first.",
                        "error_code": "PROFILE_NOT_FOUND"
                    }
                )
            ]
        ),
    },
    examples=[
        OpenApiExample(
            "Verify OTP Request",
            value={"otp_code": "123456"},
            request_only=True
        )
    ]
)
    def post(self, request):
        try:
            try:
                profile = request.user.profile
            except Profile.DoesNotExist:
                return Response({'success': False,'message': 'Profile not found. Please create your profile first.','error_code': 'PROFILE_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)
            if profile.is_phone_verified:
                return Response({'success': False,'message': 'Phone number already verified.','error_code': 'ALREADY_VERIFIED'}, status=status.HTTP_400_BAD_REQUEST)
            otp_code = request.data.get('otp_code', '').strip()
            if not otp_code:
                return Response({'success': False,'message': 'OTP code is required','errors': {'otp_code': ['This field is required']}}, status=status.HTTP_400_BAD_REQUEST)
            success, message, attempts_remaining = profile.verify_otp(otp_code)
            if not success:
                return Response({'success': False,'message': message,'data': {'attempts_remaining': attempts_remaining},'error_code': 'OTP_VERIFICATION_FAILED'}, status=status.HTTP_400_BAD_REQUEST)

            sms_service = TwilioSMSService()
            sms_service.send_verification_success(profile.phone_number, profile.name)
            logger.info(f"Phone verified successfully for user {request.user.id}")
            profile_serializer = ProfileSerializer(profile, context={'request': request})
            return Response({'success': True,'message': 'Phone number verified successfully!','data': {'profile': profile_serializer.data}}, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error in VerifyOTPView: {str(e)}")
            return Response({'success': False,'message': 'An error occurred. Please try again later.','error_code': 'INTERNAL_ERROR'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(tags=['OTP'])
class ResendOTPView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    @extend_schema(
    summary="Resend OTP",
    description="Send a new OTP to your registered phone number.",
    request=ResendOTPSerializer,
    responses={
        200: OpenApiResponse(
            description="OTP resent successfully",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "success": True,
                        "message": "OTP resent successfully.",
                        "data": {
                            "otp_expiry_minutes": 5,
                            "max_attempts": 3
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Already verified",
            examples=[
                OpenApiExample(
                    "Already Verified",
                    value={
                        "success": False,
                        "message": "Phone number already verified.",
                        "error_code": "ALREADY_VERIFIED"
                    }
                )
            ]
        ),
        404: OpenApiResponse(
            description="Profile not found",
            examples=[
                OpenApiExample(
                    "Not Found",
                    value={
                        "success": False,
                        "message": "Profile not found.",
                        "error_code": "PROFILE_NOT_FOUND"
                    }
                )
            ]
        ),
        429: OpenApiResponse(
            description="Too many OTP requests",
            examples=[
                OpenApiExample(
                    "Locked",
                    value={
                        "success": False,
                        "message": "Too many attempts. Please try again later.",
                        "error_code": "OTP_LOCKED"
                    }
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
                return Response({'success': False,'message': 'Profile not found.','error_code': 'PROFILE_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)
            
            if profile.is_phone_verified:
                return Response({'success': False,'message': 'Phone number already verified.','error_code': 'ALREADY_VERIFIED'}, status=status.HTTP_400_BAD_REQUEST)
            
            if profile.is_otp_locked():
                return Response({'success': False,'message': 'Too many attempts. Please try again later.','error_code': 'OTP_LOCKED'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            otp_code = profile.generate_otp()
            sms_service = TwilioSMSService()
            sms_success, sms_message = sms_service.send_otp(profile.phone_number, otp_code)
            
            if not sms_success:
                profile.clear_otp()
                return Response({'success': False,'message': f'Failed to send OTP: {sms_message}','error_code': 'SMS_FAILED'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            logger.info(f"OTP resent to {profile.phone_number} for user {request.user.id}")
            
            return Response({'success': True,'message': 'OTP resent successfully','data': {'otp_expiry_minutes': 5,'max_attempts': 3}}, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error in ResendOTPView: {str(e)}")
            return Response({'success': False,'message': 'An error occurred. Please try again later.','error_code': 'INTERNAL_ERROR'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(tags=['Profile'])
class ProfileDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    @extend_schema(
    summary="Get Profile Details",
    description="Retrieve the authenticated user's profile information.",
    responses={
        200: OpenApiResponse(
            description="Profile retrieved successfully",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "success": True,
                        "data": {
                            "profile": {
                                "id": 1,
                                "email": "user@example.com",
                                "name": "John Doe",
                                "age": 25,
                                "gender": "male",
                                "location": "New York, USA",
                                "phone_number": "+1234567890",
                                "is_phone_verified": True,
                                "bio": "Software Developer",
                                "profile_pic": "/media/profile_pics/image.jpg",
                                "profile_pic_url": "https://cdn.myapp.com/media/profile_pics/image.jpg",
                                "created_at": "2025-10-26T10:30:00Z",
                                "updated_at": "2025-10-26T10:35:00Z"
                            }
                        }
                    }
                )
            ]
        ),
        404: OpenApiResponse(
            description="Profile not found",
            examples=[
                OpenApiExample(
                    "Not Found",
                    value={
                        "success": False,
                        "message": "Profile not found.",
                        "error_code": "PROFILE_NOT_FOUND"
                    }
                )
            ]
        ),
    }
)
    def get(self, request):
        try:
            profile = request.user.profile
            serializer = ProfileSerializer(profile, context={'request': request})
            return Response({'success': True,'data': {'profile': serializer.data}}, status=status.HTTP_200_OK)
        except Profile.DoesNotExist:
            return Response({'success': False,'message': 'Profile not found','error_code': 'PROFILE_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)
    
    @extend_schema(
    summary="Update Profile",
    description="Update your profile details. Phone verification required. Email is read-only.",
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string', 'example': 'John Updated'},
                'age': {'type': 'integer', 'example': 26},
                'gender': {'type': 'string', 'enum': ['male', 'female', 'other', 'none']},
                'location': {'type': 'string', 'example': 'Los Angeles, USA'},
                'bio': {'type': 'string', 'example': 'Updated bio'},
                'profile_pic': {
                    'type': 'string',
                    'format': 'binary',
                    'description': 'Profile picture (max 5MB)'
                }
            }
        }
    },
    responses={
        200: OpenApiResponse(
            description="Profile updated successfully",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "success": True,
                        "message": "Profile updated successfully",
                        "data": {
                            "profile": {
                                "id": 1,
                                "email": "user@example.com",
                                "name": "John Updated",
                                "age": 26,
                                "is_phone_verified": True
                            }
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Validation error",
            examples=[
                OpenApiExample(
                    "Validation Error",
                    value={
                        "success": False,
                        "message": "Validation failed",
                        "errors": {
                            "age": ["Ensure this value is greater than or equal to 13."]
                        }
                    }
                )
            ]
        ),
        403: OpenApiResponse(
            description="Phone not verified",
            examples=[
                OpenApiExample(
                    "Not Verified",
                    value={
                        "success": False,
                        "message": "Please verify your phone number first",
                        "error_code": "PHONE_NOT_VERIFIED"
                    }
                )
            ]
        ),
        404: OpenApiResponse(
            description="Profile not found",
            examples=[
                OpenApiExample(
                    "Not Found",
                    value={
                        "success": False,
                        "message": "Profile not found",
                        "error_code": "PROFILE_NOT_FOUND"
                    }
                )
            ]
        ),
    }
)
    def patch(self, request):
        try:
            profile = request.user.profile    
            if not profile.is_phone_verified:
                return Response({'success': False,'message': 'Please verify your phone number first','error_code': 'PHONE_NOT_VERIFIED'}, status=status.HTTP_403_FORBIDDEN) 
            serializer = ProfileUpdateSerializer(profile, data=request.data, partial=True,context={'request': request})
            if not serializer.is_valid():
                return Response({'success': False,'message': 'Validation failed','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            serializer.save()
            profile_serializer = ProfileSerializer(profile, context={'request': request})
            return Response({'success': True,'message': 'Profile updated successfully','data': {'profile': profile_serializer.data}}, status=status.HTTP_200_OK)
        except Profile.DoesNotExist:
            return Response({'success': False,'message': 'Profile not found','error_code': 'PROFILE_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)