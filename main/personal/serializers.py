import re
from datetime import date
from rest_framework import serializers
from personal.models import Profile, EmergencyContact, LANGUAGE_CHOICES
from django.db import transaction
from personal.tasks import send_emergency_contact_notification_task

def validate_phone_e164(value: str) -> str:
    cleaned = re.sub(r"[\s\-\(\)]", "", value)
    if not re.fullmatch(r"\+[1-9]\d{1,14}", cleaned):
        raise serializers.ValidationError("Phone number must be in international format (e.g. +911234567890).")
    return cleaned

def validate_date_of_birth(value) -> date:
    if not value:
        raise serializers.ValidationError("Date of birth is required.")
    today = date.today()
    age = (today.year - value.year - ((today.month, today.day) < (value.month, value.day)))
    if value > today:
        raise serializers.ValidationError("Date of birth cannot be in the future.")
    if age < 13:
        raise serializers.ValidationError("You must be at least 13 years old.")
    if age > 110:
        raise serializers.ValidationError("Invalid date of birth.")
    return value

def validate_preferred_destinations(value: list) -> list:
    if not isinstance(value, list):
        raise serializers.ValidationError("Must be a list of destination strings.")
    cleaned = [str(v).strip() for v in value if str(v).strip()]
    if len(cleaned) < 2:
        raise serializers.ValidationError("Please provide at least 2 preferred destinations.")
    if len(cleaned) > 3:
        raise serializers.ValidationError("You can provide a maximum of 3 preferred destinations.")
    if len(cleaned) != len(set(d.lower() for d in cleaned)):
        raise serializers.ValidationError("Preferred destinations must be unique.")
    return cleaned

class EmergencyContactSerializer(serializers.ModelSerializer):
    class Meta:
        model  = EmergencyContact
        fields = ["id", "name", "phone_number", "email", "relation", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_phone_number(self, value: str) -> str:
        return validate_phone_e164(value)

    def validate(self, data: dict) -> dict:
        profile = self.context.get("profile")
        if profile and not self.instance:
            existing = EmergencyContact.objects.filter(profile=profile).count()
            if existing >= 3:
                raise serializers.ValidationError("A profile can have a maximum of 3 emergency contacts.")
        return data

class EmergencyContactWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    phone_number = serializers.CharField(max_length=17)
    email = serializers.EmailField()
    relation = serializers.ChoiceField(choices=["Spouse", "Parent", "Friend", "Sibling", "Other"])

    def validate_phone_number(self, value: str) -> str:
        return validate_phone_e164(value)

class ProfileCreateSerializer(serializers.Serializer):
    fname = serializers.CharField(max_length=100)
    lname = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    gender = serializers.ChoiceField(choices=["male", "female", "other"])
    date_of_birth = serializers.DateField()
    bio = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    blood_group = serializers.ChoiceField(choices=["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"])
    allergies = serializers.CharField(max_length=300, help_text="List allergies or write 'None'.",)
    medical = serializers.CharField(max_length=500, help_text="List medical conditions or write 'None'.",)
    preference = serializers.ChoiceField( choices=["relaxed", "adventurous", "nature", "cultural", "spiritual", "historic"])
    preferred_destinations = serializers.ListField(child=serializers.CharField(max_length=100),
                                                    help_text="2 to 3 preferred regions or destinations.",)
    language = serializers.ChoiceField(choices=[c[0] for c in LANGUAGE_CHOICES], default="en", required=False,)
    emergency_contacts = serializers.ListField(child=EmergencyContactWriteSerializer(), min_length=1, max_length=3,
                                                help_text="Provide 1 to 3 emergency contacts.",)

    def validate_date_of_birth(self, value):
        return validate_date_of_birth(value)

    def validate_preferred_destinations(self, value):
        return validate_preferred_destinations(value)

    def validate_allergies(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Allergies field is required. Enter 'None' if you have none.")
        return value.strip()

    def validate_medical(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Medical field is required. Enter 'None' if you have no conditions.")
        return value.strip()

    def validate_emergency_contacts(self, contacts: list) -> list:
        phones = [c["phone_number"] for c in contacts]
        emails = [c["email"].lower() for c in contacts]
        if len(phones) != len(set(phones)):
            raise serializers.ValidationError("Emergency contacts must have unique phone numbers.")
        if len(emails) != len(set(emails)):
            raise serializers.ValidationError("Emergency contacts must have unique email addresses.")
        return contacts

    def create(self, validated_data):
        user = self.context['request'].user
        contacts_data = validated_data.pop('emergency_contacts')
        with transaction.atomic():
            profile = Profile.objects.create(user=user, **validated_data)
            for contact_data in contacts_data:
                contact = EmergencyContact.objects.create(profile=profile, **contact_data)
                transaction.on_commit(lambda c=contact, u=user, p=profile: send_emergency_contact_notification_task.delay(
                    contact_email=c.email,
                    contact_name=c.name,
                    user_full_name=p.full_name,
                    user_email=u.email,
                    relation=c.relation,
                ))
        return profile

class ProfileUpdateSerializer(serializers.Serializer):
    fname = serializers.CharField(max_length=100, required=False)
    lname = serializers.CharField(max_length=100, required=False, allow_blank=True)
    gender = serializers.ChoiceField(choices=["male", "female", "other"], required=False)
    date_of_birth = serializers.DateField(required=False)
    bio = serializers.CharField(max_length=500, required=False, allow_blank=True)
    blood_group = serializers.ChoiceField(choices=["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"], required=False)
    allergies = serializers.CharField(max_length=300, required=False)
    medical = serializers.CharField(max_length=500, required=False)
    preference = serializers.ChoiceField(choices=["relaxed", "adventurous", "nature", "cultural", "spiritual", "historic"], required=False,)
    preferred_destinations = serializers.ListField(child=serializers.CharField(max_length=100), required=False,)
    language = serializers.ChoiceField( choices=[c[0] for c in LANGUAGE_CHOICES], required=False,)

    def validate_date_of_birth(self, value):
        return validate_date_of_birth(value)

    def validate_preferred_destinations(self, value):
        return validate_preferred_destinations(value)

    def validate_allergies(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Allergies field cannot be blank. Enter 'None' if you have none.")
        return value.strip()

    def validate_medical(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Medical field cannot be blank. Enter 'None' if you have none.")
        return value.strip()

class ProfileSerializer(serializers.ModelSerializer):
    email  = serializers.EmailField(source="user.email", read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    emergency_contacts = EmergencyContactSerializer(many=True, read_only=True)
    language_display = serializers.CharField(source="get_language_display", read_only=True)
    preference_display = serializers.CharField(source="get_preference_display", read_only=True)

    class Meta:
        model  = Profile
        fields = [
            "user_id", "email",
            "fname", "lname", "gender", "date_of_birth", "bio",
            "profile_pic",
            "blood_group", "allergies", "medical",
            "preference", "preference_display",
            "preferred_destinations",
            "language", "language_display",
            "emergency_contacts",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

class ProfilePublicSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        model  = Profile
        fields = [
            "user_id", "fname", "lname",
            "bio", "gender", "preference", "profile_pic",
        ]
        read_only_fields = fields

class EmergencySOSSerializer(serializers.Serializer):
    latitude  = serializers.FloatField(help_text="Current latitude from device GPS.",)
    longitude = serializers.FloatField(help_text="Current longitude from device GPS.",)
    message = serializers.CharField(max_length=500, required=False, allow_blank=True, default="", help_text="Optional message from the user.",)

    def validate_latitude(self, value: float) -> float:
        if not (-90 <= value <= 90):
            raise serializers.ValidationError("Latitude must be between -90 and 90.")
        return value

    def validate_longitude(self, value: float) -> float:
        if not (-180 <= value <= 180):
            raise serializers.ValidationError( "Longitude must be between -180 and 180.")
        return value

class ProfilePicUploadSerializer(serializers.Serializer):
    profile_pic = serializers.ImageField(help_text="Image file. Max 5MB. Formats: jpg, jpeg, png, webp.",)
    def validate_profile_pic(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Image must be smaller than 5MB.")
        ext = value.name.rsplit(".", 1)[-1].lower()
        if ext not in ["jpg", "jpeg", "png", "webp"]:
            raise serializers.ValidationError("Unsupported format. Allowed: jpg, jpeg, png, webp.")
        return value