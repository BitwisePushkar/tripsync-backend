import logging
import uuid
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError as DRFValidationError
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample, OpenApiTypes
from django.db.models import Q, Value
from django.db.models.functions import Concat
from django.db.models import CharField
from personal.models import Profile, EmergencyContact
from personal import serializers
from personal import utils
from personal import tasks

User = get_user_model()
logger = logging.getLogger("personal")

class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

def _error(message: str, errors: dict = None, status_code=status.HTTP_400_BAD_REQUEST):
    body = {"status": "error", "message": message}
    if errors:
        body["errors"] = errors
    return Response(body, status=status_code)

def _success(message: str, data: dict = None, status_code=status.HTTP_200_OK):
    body = {"status": "success", "message": message}
    if data is not None:
        body["data"] = data
    return Response(body, status=status_code)

@extend_schema(tags=["Profile"])
class ProfileDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    
    @extend_schema(
        summary="Get my profile",
        responses={
            200: serializers.ProfileSerializer,
            404: OpenApiResponse(description="Profile not found"),
        },
    )
    def get(self, request):
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return _error(
                "Profile not found. Please create your profile.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return _success("Profile retrieved.", {"profile": serializers.ProfileSerializer(profile).data})

    @extend_schema(
        summary="Create profile",
        description=("Creates the user's profile with nested emergency contacts (1-3)."),
        request=serializers.ProfileCreateSerializer,
        responses={
            201: serializers.ProfileSerializer,
            400: OpenApiResponse(description="Validation error or profile already exists"),
        },
        examples=[
            OpenApiExample(
                "Create profile request",
                value={
                    "fname": "Pushkar",
                    "lname": "Singhal",
                    "gender": "male",
                    "date_of_birth": "1998-05-15",
                    "bio": "Love exploring mountains.",
                    "blood_group": "O+",
                    "allergies": "Peanuts",
                    "medical": "None",
                    "preference": "adventurous",
                    "preferred_destinations": ["Himalayas", "Patagonia"],
                    "language": "en",
                    "emergency_contacts": [
                        {
                            "name": "Priya Singhal",
                            "phone_number": "+911234567890",
                            "email": "priya@example.com",
                            "relation": "Parent",
                        }
                    ],
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        if hasattr(request.user, "profile"):
            return _error(
                "Profile already exists. Use PATCH to update.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        serializer = serializers.ProfileCreateSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        data = serializer.validated_data
        contacts_data = data.pop("emergency_contacts")
        profile = Profile.objects.create(user=request.user, **data)
        for contact_data in contacts_data:
            contact = EmergencyContact.objects.create(profile=profile, **contact_data)
            tasks.send_emergency_contact_notification_task.delay(
                contact_email=contact.email,
                contact_name=contact.name,
                user_full_name=profile.full_name,
                user_email=request.user.email,
                relation=contact.relation,
            )
        logger.info("Profile created for user %s", request.user.email)
        return _success(
            "Profile created successfully.",
            {"profile": serializers.ProfileSerializer(profile).data},
            status_code=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Update profile (partial)",
        description=("Partially update profile fields. All fields are optional."),
        request=serializers.ProfileUpdateSerializer,
        responses={
            200: serializers.ProfileSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Profile not found"),
        },
    )
    def patch(self, request):
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return _error(
                "Profile not found. Please create your profile first.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        serializer = serializers.ProfileUpdateSerializer(data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        data = serializer.validated_data
        for field, value in data.items():
            setattr(profile, field, value)
        profile.save()
        logger.info("Profile updated for user %s", request.user.email)
        return _success(
            "Profile updated successfully.",
            {"profile": serializers.ProfileSerializer(profile).data},
        )

@extend_schema(tags=["Profile"])
class ProfilePictureView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    @extend_schema(
        summary="Upload profile picture",
        description=("Upload a profile picture via multipart/form-data."),
        request=serializers.ProfilePicUploadSerializer,
        responses={
            200: OpenApiResponse(description="Picture uploaded — S3 URL returned"),
            400: OpenApiResponse(description="Invalid file"),
            404: OpenApiResponse(description="Profile not found"),
        },
    )
    def post(self, request):
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return _error(
                "Profile not found. Create your profile before uploading a picture.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        serializer = serializers.ProfilePicUploadSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        image_file = serializer.validated_data["profile_pic"]
        if profile.profile_pic:
            old_key = utils.extract_s3_key_from_url(profile.profile_pic)
            if old_key:
                utils.delete_image_from_s3(old_key)
        ext = image_file.name.rsplit(".", 1)[-1].lower()
        s3_key = f"profile_pics/user_{request.user.id}_{uuid.uuid4().hex}.{ext}"
        success, result = utils.upload_image_to_s3(image_file, s3_key)
        if not success:
            return _error(
                f"Failed to upload image: {result}",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        profile.profile_pic = result 
        profile.save(update_fields=["profile_pic", "updated_at"])
        logger.info("Profile picture uploaded for user %s: %s", request.user.email, s3_key)
        return _success("Profile picture uploaded.", {"profile_pic_url": result})

    @extend_schema(
        summary="Remove profile picture",
        responses={200: OpenApiResponse(description="Picture removed")},
    )
    def delete(self, request):
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return _error("Profile not found.", status_code=status.HTTP_404_NOT_FOUND)

        if not profile.profile_pic:
            return _error("No profile picture to remove.")

        s3_key = utils.extract_s3_key_from_url(profile.profile_pic)
        if s3_key:
            utils.delete_image_from_s3(s3_key)

        profile.profile_pic = ""
        profile.save(update_fields=["profile_pic", "updated_at"])
        return _success("Profile picture removed.")

@extend_schema(tags=["Emergency"])
class EmergencyContactListView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    @extend_schema(
        summary="List emergency contacts",
        responses={200: serializers.EmergencyContactSerializer(many=True)},
    )
    def get(self, request):
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return _error("Profile not found.", status_code=status.HTTP_404_NOT_FOUND)

        contacts = profile.emergency_contacts.all()
        return _success(
            "Emergency contacts retrieved.",
            {
                "contacts": serializers.EmergencyContactSerializer(contacts, many=True).data,
                "count": contacts.count(),
                "can_add_more": contacts.count() < 3,
            },
        )

    @extend_schema(
        summary="Add emergency contact",
        description=(
            "Add a new emergency contact. Maximum 3 per profile.\n\n"
            "A notification email is sent to the contact immediately."
        ),
        request=serializers.EmergencyContactSerializer,
        responses={
            201: serializers.EmergencyContactSerializer,
            400: OpenApiResponse(description="Validation error or max contacts reached"),
        },
        examples=[
            OpenApiExample(
                "Add contact request",
                value={
                    "name": "Priya Singhal",
                    "phone_number": "+911234567890",
                    "email": "priya@example.com",
                    "relation": "Parent",
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return _error("Profile not found.", status_code=status.HTTP_404_NOT_FOUND)

        if profile.emergency_contacts.count() >= 3:
            return _error(
                "Maximum of 3 emergency contacts allowed. "
                "Please remove one before adding another.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = serializers.EmergencyContactSerializer(data=request.data, context={"profile": profile},)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        contact = serializer.save(profile=profile)
        tasks.send_emergency_contact_notification_task.delay(
            contact_email=contact.email,
            contact_name=contact.name,
            user_full_name=profile.full_name,
            user_email=request.user.email,
            relation=contact.relation,
        )
        logger.info("Emergency contact added for user %s: %s", request.user.email, contact.email,)
        return _success(
            "Emergency contact added. A notification email has been sent to them.",
            {"contact": serializers.EmergencyContactSerializer(contact).data},
            status_code=status.HTTP_201_CREATED,
        )

@extend_schema(tags=["Emergency"])
class EmergencyContactDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    def _get_contact(self, request, pk: int):
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return None, _error("Profile not found.", status_code=status.HTTP_404_NOT_FOUND)

        try:
            contact = EmergencyContact.objects.get(pk=pk, profile=profile)
            return contact, None
        except EmergencyContact.DoesNotExist:
            return None, _error("Emergency contact not found.", status_code=status.HTTP_404_NOT_FOUND,)

    @extend_schema(
        summary="Update emergency contact",
        request=serializers.EmergencyContactSerializer,
        responses={
            200: serializers.EmergencyContactSerializer,
            404: OpenApiResponse(description="Contact not found"),
        },
    )
    def patch(self, request, pk: int):
        contact, err = self._get_contact(request, pk)
        if err:
            return err
        serializer = serializers.EmergencyContactSerializer(contact, data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        serializer.save()
        return _success("Emergency contact updated.", {"contact": serializer.data},)

    @extend_schema(
        summary="Remove emergency contact",
        description="Profile must retain at least 1 emergency contact.",
        responses={
            200: OpenApiResponse(description="Contact removed"),
            400: OpenApiResponse(description="Cannot remove — minimum 1 required"),
            404: OpenApiResponse(description="Contact not found"),
        },
    )
    def delete(self, request, pk: int):
        contact, err = self._get_contact(request, pk)
        if err:
            return err
        profile = request.user.profile
        if profile.emergency_contacts.count() <= 1:
            return _error("You must have at least 1 at all times.",)
        contact.delete()
        logger.info("Emergency contact removed for user %s (contact pk=%d)", request.user.email, pk,)
        return _success("Emergency contact removed.")

@extend_schema(tags=["Emergency"])
class EmergencySOSView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    @extend_schema(
        summary="Trigger emergency SOS",
        description=("Send emergency alert emails to all registered emergency contacts."),
        request=serializers.EmergencySOSSerializer,
        responses={
            200: OpenApiResponse(
                description="Alerts dispatched",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={
                            "status": "success",
                            "message": "Emergency alerts sent to 2 contact(s).",
                            "data": {
                                "alerts_sent": 2,
                                "contacts_notified": [
                                    "priya@example.com",
                                    "ravi@example.com",
                                ],
                            },
                        },
                    )
                ],
            ),
            400: OpenApiResponse(description="Validation error or no emergency contacts"),
            404: OpenApiResponse(description="Profile not found"),
        },
        examples=[
            OpenApiExample(
                "SOS request",
                value={
                    "latitude": 28.6139,
                    "longitude": 77.2090,
                    "message": "I am stuck near the trail. Please send help.",
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return _error(
                "Profile not found. Please create your profile first.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        contacts = profile.emergency_contacts.all()
        if not contacts.exists():
            return _error(
                "No emergency contacts found. "
                "Please add at least one emergency contact before using SOS.",
            )
        serializer = serializers.EmergencySOSSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError:
            raise
        latitude = serializer.validated_data["latitude"]
        longitude = serializer.validated_data["longitude"]
        custom_message = serializer.validated_data.get("message", "")
        notified_emails = []
        for contact in contacts:
            tasks.send_emergency_alert_task.delay(
                contact_email=contact.email,
                contact_name=contact.name,
                user_full_name=profile.full_name,
                user_email=request.user.email,
                blood_group=profile.blood_group,
                allergies=profile.allergies,
                medical=profile.medical,
                profile_pic_url=profile.profile_pic or "",
                latitude=latitude,
                longitude=longitude,
                custom_message=custom_message,
            )
            notified_emails.append(contact.email)
        logger.info("Emergency SOS triggered by user %s — %d contact(s) notified", request.user.email, len(notified_emails),)
        return _success(
            f"Emergency alerts sent to {len(notified_emails)} contact(s).",
            {
                "alerts_sent": len(notified_emails),
                "contacts_notified": notified_emails,
            },
        )

@extend_schema(tags=["Users"])
class UserSearchView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    @extend_schema(
        summary="Search users by name",
        description=("Search users by name using `?q=<query>`."),
        parameters=[
            {
                "name": "q",
                "in": "query",
                "required": True,
                "schema": {"type": "string"},
                "description": "Name search query (min 2 characters).",
            }
        ],
        responses={
            200: serializers.ProfilePublicSerializer(many=True),
            400: OpenApiResponse(description="Query param missing or too short"),
            404: OpenApiResponse(description="No users found"),
        },
    )
    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if not q:
            return _error(
                "Search query is required. Use ?q=name",
                errors={"q": ["This field is required."]},
            )
        if len(q) < 2:
            return _error(
                "Search query must be at least 2 characters.",
                errors={"q": ["Minimum 2 characters required."]},
            )
        qs = (
            Profile.objects
            .select_related("user")
            .annotate(
                full_name_combined=Concat(
                    "fname", Value(" "), "lname",
                    output_field=CharField(),
                )
            )
            .filter(
                Q(fname__icontains=q) |
                Q(lname__icontains=q) |
                Q(full_name_combined__icontains=q)
            )
            .order_by("fname", "lname")
        )
        if not qs.exists():
            return _error(
                f"No users found matching '{q}'.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        count = qs.count()
        return _success(
            f"{count} user{'s' if count != 1 else ''} found.",
            {
                "count": count,
                "users": serializers.ProfilePublicSerializer(qs, many=True).data,
            },
        )