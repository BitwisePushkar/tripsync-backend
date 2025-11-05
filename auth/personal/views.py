from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse, inline_serializer
from drf_spectacular.types import OpenApiTypes
from .models import Profile
from .serializers import (UserListSerializer, UserProfileSearchSerializer, UserProfileDetailSerializer,ProfileCreateSerializer,OTPVerificationSerializer,ProfileUpdateSerializer,ResendOTPSerializer,ProfileSerializer,EmergencySOSSerializer)
from .utils import SMSService
import logging

logger = logging.getLogger(__name__)

@extend_schema(tags=['Profile'])
class ProfileDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    @extend_schema(
    summary="Create Complete Profile & Send OTP",
    description=("Create a complete profile with personal info,"),
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'fname': {'type': 'string', 'example': 'John'},
                'lname': {'type': 'string', 'example': 'Doe'},
                'phone_number': {'type': 'string', 'example': '+1234567890'},
                'date': {'type': 'string', 'format': 'date', 'example': '1998-05-15'},
                'gender': {'type': 'string', 'enum': ['male', 'female', 'other'], 'example': 'male'},
                'bio': {'type': 'string', 'example': 'Software Developer'},
                'profile_pic': {'type': 'string', 'format': 'binary', 'description': 'Optional photo (max 5MB)'},
                'bgroup': {'type': 'string', 'enum': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'], 'example': 'O+'},
                'allergies': {'type': 'string', 'example': 'Peanuts, Dust'},
                'medical': {'type': 'string', 'example': 'Asthma, takes inhaler'},
                'ename': {'type': 'string', 'example': 'Jane Doe'},
                'enumber': {'type': 'string', 'example': '+1987654321'},
                'erelation': {'type': 'string', 'enum': ['Spouse', 'Parent', 'Friend', 'Sibling'], 'example': 'Spouse'},
                'prefrence': {'type': 'string', 'enum': ['Adventure', 'Relaxation', 'Nature', 'Explore', 'Spiritual', 'Historic'], 'example': 'Adventure'}
            },
            'required': ['fname', 'lname', 'phone_number']
        }
    },
    responses={
        201: OpenApiResponse(
            description="Profile created and OTP sent successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "success": True,
                        "message": "Profile created successfully. OTP sent for verification.",
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
            description="Validation error or profile exists",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Profile Exists",
                    value={
                        "success": False,
                        "message": "Profile already exists.",
                        "error_code": "PROFILE_EXISTS"
                    }
                ),
                OpenApiExample(
                    "Validation Failed",
                    value={
                        "success": False,
                        "message": "Validation failed",
                        "errors": {
                            "phone_number": ["This field is required."]
                        }
                    }
                )
            ]
        ),
        429: OpenApiResponse(
            description="Too many OTP attempts",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "OTP Locked",
                    value={
                        "success": False,
                        "message": "Too many attempts. Please try again later.",
                        "error_code": "OTP_LOCKED"
                    }
                )
            ]
        ),
        500: OpenApiResponse(
            description="Internal error or SMS sending failed",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "SMS Failed",
                    value={
                        "success": False,
                        "message": "Failed to send OTP: <error_message>",
                        "error_code": "SMS_FAILED"
                    }
                ),
                OpenApiExample(
                    "Internal Error",
                    value={
                        "success": False,
                        "message": "An error occurred. Please try again later.",
                        "error_code": "INTERNAL_ERROR"
                    }
                )
            ]
        )
    }
    )
    def post(self, request):
        try:
            if hasattr(request.user, 'profile'):
                return Response({'success': False,'message': 'Profile already exists','error_code': 'PROFILE_EXISTS'}, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = ProfileCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({'success': False,'message': 'Validation failed','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            validated_data = serializer.validated_data
            phone_number = validated_data['phone_number']
            profile_pic = request.FILES.get('profile_pic')
            profile = Profile.objects.create(user=request.user,is_phone_verified=False,fname=validated_data['fname'],lname=validated_data['lname'],phone_number=phone_number,
                date=validated_data.get('date'),gender=validated_data.get('gender', ''),bio=validated_data.get('bio', ''),bgroup=validated_data.get('bgroup', ''),allergies=validated_data.get('allergies', ''),
                medical=validated_data.get('medical', ''),ename=validated_data.get('ename', ''),enumber=validated_data.get('enumber', ''),erelation=validated_data.get('erelation', ''),prefrence=validated_data.get('prefrence', ''))
            
            profile_pic_uploaded = False
            if profile_pic:
                profile.profile_pic = profile_pic
                profile.save()
                profile_pic_uploaded = True
            
            if profile.is_otp_locked():
                profile.delete()
                return Response({'success': False,'message': 'Too many attempts. Please try again later.','error_code': 'OTP_LOCKED'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            otp_code = profile.generate_otp()
            sms_service = SMSService()
            sms_success, sms_message = sms_service.send_otp(phone_number, otp_code)
            
            if not sms_success:
                profile.delete()
                return Response({'success': False,'message': f'Failed to send OTP: {sms_message}','error_code': 'SMS_FAILED'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            logger.info(f"Complete profile created and OTP sent to {phone_number} for user {request.user.id}")
            return Response({'success': True,'message': 'Profile created successfully. OTP sent for verification.','data': {'phone_number': phone_number,'otp_expiry_minutes': 5,'max_attempts': 3,'profile_pic_uploaded': profile_pic_uploaded}}, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            logger.error(f"Error in ProfileDetailView POST: {str(e)}")
            return Response({'success': False,'message': 'An error occurred. Please try again later.','error_code': 'INTERNAL_ERROR'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
    summary="Get Profile Details",
    description="Retrieve the authenticated user's complete profile information.",
    responses={
        200: OpenApiResponse(
            description="Profile retrieved successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "success": True,
                        "data": {
                            "profile": {
                                "fname": "John",
                                "lname": "Doe",
                                "phone_number": "+1234567890",
                                "date": "1998-05-15",
                                "gender": "male",
                                "bio": "Software Developer",
                                "profile_pic": "https://cdn.example.com/profile_pic.jpg",
                                "bgroup": "O+",
                                "allergies": "Peanuts, Dust",
                                "medical": "Asthma, takes inhaler",
                                "ename": "Jane Doe",
                                "enumber": "+1987654321",
                                "erelation": "Spouse",
                                "prefrence": "Adventure",
                                "is_phone_verified": False
                            }
                        }
                    }
                )
            ]
        ),
        404: OpenApiResponse(
            description="Profile not found",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Not Found Example",
                    value={
                        "success": False,
                        "message": "Profile not found",
                        "error_code": "PROFILE_NOT_FOUND"
                    }
                )
            ]
        )
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
    description="Update profile details. Phone verification required.",
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'fname': {'type': 'string', 'example': 'John'},
                'lname': {'type': 'string', 'example': 'Doe'},
                'date': {'type': 'string', 'format': 'date', 'example': '1998-05-15'},
                'gender': {'type': 'string', 'example': 'male'},
                'bio': {'type': 'string', 'example': 'Software Developer'},
                'profile_pic': {'type': 'string', 'format': 'binary', 'description': 'Optional photo (max 5MB)'},
                'bgroup': {'type': 'string', 'example': 'O+'},
                'allergies': {'type': 'string', 'example': 'Peanuts, Dust'},
                'medical': {'type': 'string', 'example': 'Asthma, takes inhaler'},
                'ename': {'type': 'string', 'example': 'Jane Doe'},
                'enumber': {'type': 'string', 'example': '+1987654321'},
                'erelation': {'type': 'string', 'example': 'Spouse'},
                'prefrence': {'type': 'string', 'example': 'Adventure'}
            }
        }
    },
    responses={
        200: OpenApiResponse(
            description="Profile updated successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "success": True,
                        "message": "Profile updated successfully",
                        "data": {
                            "profile": {
                                "fname": "John",
                                "lname": "Doe",
                                "phone_number": "+1234567890",
                                "date": "1998-05-15",
                                "gender": "male",
                                "bio": "Software Developer",
                                "profile_pic": "https://cdn.example.com/profile_pic.jpg",
                                "bgroup": "O+",
                                "allergies": "Peanuts, Dust",
                                "medical": "Asthma, takes inhaler",
                                "ename": "Jane Doe",
                                "enumber": "+1987654321",
                                "erelation": "Spouse",
                                "prefrence": "Adventure",
                                "is_phone_verified": True
                            }
                        }
                    }
                )
            ]
        ),
        403: OpenApiResponse(
            description="Phone not verified",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Phone Not Verified",
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
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Profile Not Found",
                    value={
                        "success": False,
                        "message": "Profile not found",
                        "error_code": "PROFILE_NOT_FOUND"
                    }
                )
            ]
        )
    }
    )
    def patch(self, request):
        try:
            profile = request.user.profile
            if not profile.is_phone_verified:
                return Response({'success': False,'message': 'Please verify your phone number first','error_code': 'PHONE_NOT_VERIFIED'}, status=status.HTTP_403_FORBIDDEN)
            serializer = ProfileUpdateSerializer(profile,data=request.data,partial=True,context={'request': request})
            
            if not serializer.is_valid():
                return Response({'success': False,'message': 'Validation failed','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            serializer.save()
            profile_serializer = ProfileSerializer(profile, context={'request': request})
            return Response({'success': True,'message': 'Profile updated successfully','data': {'profile': profile_serializer.data}}, status=status.HTTP_200_OK)
        
        except Profile.DoesNotExist:
            return Response({'success': False,'message': 'Profile not found','error_code': 'PROFILE_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)

class VerifyOTPView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser] 
    @extend_schema(
    tags=['Profile'],
    summary="Verify OTP",
    description="Verify the OTP sent to your phone number.",
    request=inline_serializer(name="VerifyOTPRequest",fields={"otp_code": OpenApiTypes.STR}),
    responses={
        200: OpenApiResponse(
            description="OTP verified successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "success": True,
                        "message": "Phone number verified successfully!",
                        "data": {
                            "profile": {
                                "fname": "John",
                                "lname": "Doe",
                                "phone_number": "+1234567890",
                                "date": "1998-05-15",
                                "gender": "male",
                                "bio": "Software Developer",
                                "profile_pic": "https://cdn.example.com/profile_pic.jpg",
                                "bgroup": "O+",
                                "allergies": "Peanuts, Dust",
                                "medical": "Asthma, takes inhaler",
                                "ename": "Jane Doe",
                                "enumber": "+1987654321",
                                "erelation": "Spouse",
                                "prefrence": "Adventure",
                                "is_phone_verified": True
                            }
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Invalid or expired OTP",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "OTP Missing",
                    value={
                        "success": False,
                        "message": "OTP code is required",
                        "errors": {"otp_code": ["This field is required"]},
                        "error_code": "OTP_VERIFICATION_FAILED"
                    }
                ),
                OpenApiExample(
                    "OTP Incorrect",
                    value={
                        "success": False,
                        "message": "Incorrect OTP code",
                        "data": {"attempts_remaining": 2},
                        "error_code": "OTP_VERIFICATION_FAILED"
                    }
                ),
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
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Profile Not Found",
                    value={
                        "success": False,
                        "message": "Profile not found. Please create your profile first.",
                        "error_code": "PROFILE_NOT_FOUND"
                    }
                )
            ]
        ),
        500: OpenApiResponse(
            description="Internal server error",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Internal Error",
                    value={
                        "success": False,
                        "message": "An error occurred. Please try again later.",
                        "error_code": "INTERNAL_ERROR"
                    }
                )
            ]
        )
    }
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
            
            sms_service = SMSService()
            sms_service.send_verification_success(profile.phone_number, profile.fname)
            logger.info(f"Phone verified successfully for user {request.user.id}")
            
            profile_serializer = ProfileSerializer(profile, context={'request': request})
            return Response({'success': True,'message': 'Phone number verified successfully!','data': {'profile': profile_serializer.data}}, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error in VerifyOTPView: {str(e)}")
            return Response({'success': False,'message': 'An error occurred. Please try again later.','error_code': 'INTERNAL_ERROR'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ResendOTPView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    @extend_schema(
    tags=['Profile'],
    summary="Resend OTP",
    description="Send a new OTP to your registered phone number.",
    responses={
        200: OpenApiResponse(
            description="OTP resent successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "success": True,
                        "message": "OTP resent successfully",
                        "data": {
                            "otp_expiry_minutes": 5,
                            "max_attempts": 3
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Phone number already verified",
            response=OpenApiTypes.OBJECT,
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
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Profile Not Found",
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
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "OTP Locked",
                    value={
                        "success": False,
                        "message": "Too many attempts. Please try again later.",
                        "error_code": "OTP_LOCKED"
                    }
                )
            ]
        ),
        500: OpenApiResponse(
            description="Internal server error",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Internal Error",
                    value={
                        "success": False,
                        "message": "An error occurred. Please try again later.",
                        "error_code": "INTERNAL_ERROR"
                    }
                )
            ]
        )
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
            sms_service = SMSService()
            sms_success, sms_message = sms_service.send_otp(profile.phone_number, otp_code)
            
            if not sms_success:
                profile.clear_otp()
                return Response({'success': False,'message': f'Failed to send OTP: {sms_message}','error_code': 'SMS_FAILED'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            logger.info(f"OTP resent to {profile.phone_number} for user {request.user.id}")
            return Response({'success': True,'message': 'OTP resent successfully','data': {'otp_expiry_minutes': 5, 'max_attempts': 3}}, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error in ResendOTPView: {str(e)}")
            return Response({'success': False,'message': 'An error occurred. Please try again later.','error_code': 'INTERNAL_ERROR'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(tags=['Emergency'])
class EmergencySOSView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    @extend_schema(
    summary="Send Emergency SOS",
    description="Send emergency alert message to your registered emergency contact number.",
    request=EmergencySOSSerializer,
    responses={
        200: OpenApiResponse(
            description="Emergency message sent successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "success": True,
                        "message": "Emergency alert sent successfully",
                        "data": {
                            "sent_to": "+1987654321",
                            "contact_name": "Jane Doe",
                            "relation": "Spouse"
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="No emergency contact configured or validation error",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "No Contact",
                    value={
                        "success": False,
                        "message": "No emergency contact configured. Please add emergency contact in your profile.",
                        "error_code": "NO_EMERGENCY_CONTACT"
                    }
                ),
                OpenApiExample(
                    "Validation Failed",
                    value={
                        "success": False,
                        "message": "Validation failed",
                        "errors": {
                            "message": ["This field may not be blank."],
                            "location": ["This field may not be blank."]
                        }
                    }
                )
            ]
        ),
        403: OpenApiResponse(
            description="Phone not verified",
            response=OpenApiTypes.OBJECT,
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
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Profile Not Found",
                    value={
                        "success": False,
                        "message": "Profile not found. Please create your profile first.",
                        "error_code": "PROFILE_NOT_FOUND"
                    }
                )
            ]
        ),
        500: OpenApiResponse(
            description="Internal server error",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Internal Error",
                    value={
                        "success": False,
                        "message": "An error occurred. Please try again later.",
                        "error_code": "INTERNAL_ERROR"
                    }
                ),
                OpenApiExample(
                    "SMS Failed",
                    value={
                        "success": False,
                        "message": "Failed to send emergency alert: SMS service error",
                        "error_code": "SMS_FAILED"
                    }
                )
            ]
        )
    },
    examples=[
        OpenApiExample(
            "With Custom Message",
            value={
                "message": "I need help! Please check on me.",
                "location": "Near Central Park, New York"
            },
            request_only=True
        ),
        OpenApiExample(
            "Default Message",
            value={},
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
            if not profile.is_phone_verified:
                return Response({'success': False,'message': 'Please verify your phone number first','error_code': 'PHONE_NOT_VERIFIED'}, status=status.HTTP_403_FORBIDDEN)
            if not profile.enumber or not profile.ename:
                return Response({'success': False,'message': 'No emergency contact configured. Please add emergency contact in your profile.','error_code': 'NO_EMERGENCY_CONTACT'}, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = EmergencySOSSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({'success': False,'message': 'Validation failed','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            custom_message = serializer.validated_data.get('message', '')
            location = serializer.validated_data.get('location', '')
            sms_service = SMSService()
            sms_success, sms_message = sms_service.send_emergency_alert(emergency_number=profile.enumber,user_name=f"{profile.fname} {profile.lname}",user_phone=profile.phone_number,custom_message=custom_message,location=location)
            
            if not sms_success:
                return Response({'success': False,'message': f'Failed to send emergency alert: {sms_message}','error_code': 'SMS_FAILED'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            logger.info(f"Emergency SOS sent from user {request.user.id} to {profile.enumber}")
            return Response({'success': True,'message': 'Emergency alert sent successfully','data': {'sent_to': profile.enumber,'contact_name': profile.ename,'relation': profile.erelation if profile.erelation else 'Not specified'}}, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error in EmergencySOSView: {str(e)}")
            return Response({'success': False,'message': 'An error occurred. Please try again later.','error_code': 'INTERNAL_ERROR'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class UserListView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]   
    @extend_schema(
    tags=['Profile'],
    summary="List All Verified Users",
    description="Returns a list of all users who have completed phone verification.",
    responses={
        200: OpenApiResponse(
            description="List of verified users retrieved successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Success",
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
                    }
                )
            ]
        ),
        403: OpenApiResponse(
            description="User's own phone not verified",
            response=OpenApiTypes.OBJECT,
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
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Profile Not Found",
                    value={
                        "success": False,
                        "message": "Profile not found. Please create your profile first.",
                        "error_code": "PROFILE_NOT_FOUND"
                    }
                )
            ]
        ),
        500: OpenApiResponse(
            description="Internal server error",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Internal Error",
                    value={
                        "success": False,
                        "message": "An error occurred. Please try again later.",
                        "error_code": "INTERNAL_ERROR"
                    }
                )
            ]
        )
    }
    )
    def get(self, request):
        try:
            try:
                profile = request.user.profile
                if not profile.is_phone_verified:
                    return Response({'success': False,'message': 'Please verify your phone number first','error_code': 'PHONE_NOT_VERIFIED'}, status=status.HTTP_403_FORBIDDEN)
            except Profile.DoesNotExist:
                return Response({'success': False,'message': 'Profile not found. Please create your profile first.','error_code': 'PROFILE_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)
            verified_users = Profile.objects.filter(is_phone_verified=True).select_related('user').order_by('fname', 'lname')
            
            serializer = UserListSerializer(verified_users, many=True)
            return Response({'success': True,'message': 'Users retrieved successfully','data': {'users': serializer.data,'count': verified_users.count()}}, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error in UserListView: {str(e)}")
            return Response({'success': False,'message': 'An error occurred. Please try again later.','error_code': 'INTERNAL_ERROR'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserProfileByNameView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]   
    @extend_schema(
        tags=['Profile'],
        summary="Get User Profiles by Name",
        description="Search for verified users by their first and last name.",
        request=UserProfileSearchSerializer,
        responses={
            200: OpenApiResponse(
                description="User profile(s) found",
                examples=[
                    OpenApiExample(
                        "Single User Found",
                        value={
                            "success": True,
                            "message": "1 user found with the provided name",
                            "data": {
                                "count": 1,
                                "users": [
                                    {
                                        "id": 1,
                                        "email": "john@example.com",
                                        "fname": "John",
                                        "lname": "Doe",
                                        "phone_number": "+1234567890",
                                        "date": "1998-05-15",
                                        "gender": "male",
                                        "bio": "Software Developer",
                                        "profile_pic_url": "https://example.com/media/profile_pics/pic.jpg",
                                        "bgroup": "O+",
                                        "allergies": "Peanuts",
                                        "medical": "Asthma",
                                        "ename": "Jane Doe",
                                        "enumber": "+1987654321",
                                        "erelation": "Spouse",
                                        "prefrence": "Adventure"
                                    }
                                ]
                            }
                        }
                    ),
                    OpenApiExample(
                        "Multiple Users Found",
                        value={
                            "success": True,
                            "message": "2 users found with the provided name",
                            "data": {
                                "count": 2,
                                "users": [
                                    {
                                        "id": 1,
                                        "email": "john.doe1@example.com",
                                        "fname": "John",
                                        "lname": "Doe",
                                        "phone_number": "+1234567890",
                                        "bio": "Software Developer"
                                    },
                                    {
                                        "id": 5,
                                        "email": "john.doe2@example.com",
                                        "fname": "John",
                                        "lname": "Doe",
                                        "phone_number": "+1987654321",
                                        "bio": "Data Scientist"
                                    }
                                ]
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Validation error",
                examples=[OpenApiExample(
                    "Missing Fields",
                    value={
                        "success": False,
                        "message": "Validation failed",
                        "errors": {
                            "fname": ["This field is required."]
                        }
                    }
                )]
            ),
            403: OpenApiResponse(
                description="User's own phone not verified"
            ),
            404: OpenApiResponse(
                description="User not found",
                examples=[OpenApiExample(
                    "Not Found",
                    value={
                        "success": False,
                        "message": "No verified user found with the provided name",
                        "error_code": "USER_NOT_FOUND"
                    }
                )]
            )
        },
        examples=[
            OpenApiExample(
                "Search Request",
                value={
                    "fname": "John",
                    "lname": "Doe"
                },
                request_only=True
            )
        ]
    )
    def post(self, request):
        try:
            try:
                profile = request.user.profile
                if not profile.is_phone_verified:
                    return Response({'success': False,'message': 'Please verify your phone number','error_code': 'PHONE_NOT_VERIFIED'}, status=status.HTTP_403_FORBIDDEN)
            except Profile.DoesNotExist:
                return Response({'success': False,'message': 'Profile not found.','error_code': 'PROFILE_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)
            serializer = UserProfileSearchSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({'success': False,'message': 'Validation failed','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            fname = serializer.validated_data['fname'].strip()
            lname = serializer.validated_data['lname'].strip()
            user_profiles = Profile.objects.select_related('user').filter(fname__iexact=fname,lname__iexact=lname,is_phone_verified=True).order_by('id')  
            if not user_profiles.exists():
                return Response({'success': False,'message': 'No verified user found ','error_code': 'USER_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)
            profile_serializer = UserProfileDetailSerializer(user_profiles,many=True, context={'request': request})          
            user_count = user_profiles.count()
            message = f"{user_count} user{'s' if user_count > 1 else ''} found with the provided name"          
            logger.info(f"User {request.user.id} retrieved {user_count} profile(s) for {fname} {lname}")          
            return Response({'success': True,'message': message,'data': {'count': user_count,'users': profile_serializer.data}}, status=status.HTTP_200_OK)     
        except Exception as e:
            logger.error(f"Error in UserProfileByNameView: {str(e)}")
            return Response({'success': False,'message': 'An error occurred.','error_code': 'INTERNAL_ERROR'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)