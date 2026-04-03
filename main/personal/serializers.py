from rest_framework import serializers
from .models import Profile
from django.contrib.auth import get_user_model
from datetime import date
import re

def get_s3_url(obj_field):
    if obj_field:
        try:
            return obj_field.url
        except Exception:
            return None
    return None

User = get_user_model()

def validate_age(value):
    if not value:
        raise serializers.ValidationError("Date of birth is required")
    today = date.today()
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if value > today:
        raise serializers.ValidationError("Date of birth cannot be in the future")
    if age < 13:
        raise serializers.ValidationError("You must be at least 13 years old")
    if age > 110:
        raise serializers.ValidationError("Invalid date of birth. Maximum age is 110 years")
    return value

def validate_phone_format(value):
    cleaned = re.sub(r'[^\d+]', '', value)
    if not re.match(r'^\+[1-9]\d{1,14}$', cleaned):
        raise serializers.ValidationError("Phone number must be in international format (e.g., +1234567890)")
    return cleaned

class ProfileSerializer(serializers.ModelSerializer):
    profile_pic_url = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    id = serializers.IntegerField(source='user.id', read_only=True)
    class Meta:
        model = Profile
        fields = [
            'id', 'email', 'fname', 'lname', 'phone_number', 'is_phone_verified',
            'date', 'gender', 'bio', 'profile_pic', 'profile_pic_url',
            'bgroup', 'allergies', 'medical', 'ename', 'enumber', 'erelation',
            'prefrence', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'email', 'is_phone_verified', 'created_at', 'updated_at']
        extra_kwargs = {
           'profile_pic': {'write_only': True}
           }

    def get_profile_pic_url(self, obj):
       return get_s3_url(obj.profile_pic)

    def validate_phone_number(self, value):
        value = re.sub(r'[^\d+]', '', value)
        if not re.fullmatch(r'\+[1-9]\d{1,14}', value):
            raise serializers.ValidationError("Use international format (e.g., +1234567890)")
        qs = Profile.objects.filter(phone_number=value)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("This phone number is already registered")
        return value

    def validate_date(self, value):
        return validate_age(value)

    def validate_enumber(self, value):
        if value:
            value = re.sub(r'[^\d+]', '', value)
            if not re.fullmatch(r'\+[1-9]\d{1,14}', value):
                raise serializers.ValidationError("Emergency number must be in international format (e.g., +1234567890)")
        return value

    def validate_profile_pic(self, value):
        if value:
            if value.size > 5 * 1024 * 1024:
                raise serializers.ValidationError("Profile picture size must be less than 5MB")
            ext = value.name.split('.')[-1].lower()
            if ext not in ['jpg', 'jpeg', 'png', 'webp']:
                raise serializers.ValidationError("Unsupported file format. Allowed formats: jpg, jpeg, png, webp")
        return value

class ProfileCreateSerializer(serializers.Serializer):
    fname = serializers.CharField(max_length=100)
    lname = serializers.CharField(max_length=100)
    phone_number = serializers.CharField(max_length=17)
    date = serializers.DateField(required=True, allow_null=False)
    gender = serializers.ChoiceField(choices=['male', 'female', 'other'], required=True, allow_blank=False)
    bio = serializers.CharField(max_length=500, required=True, allow_blank=False)
    bgroup = serializers.ChoiceField(choices=['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],required=True, allow_blank=False)
    allergies = serializers.CharField(max_length=200, required=False, allow_blank=True)
    medical = serializers.CharField(max_length=500, required=False, allow_blank=True)
    ename = serializers.CharField(max_length=100, required=True, allow_blank=False)
    enumber = serializers.CharField(max_length=17, required=True, allow_blank=False)
    erelation = serializers.ChoiceField(choices=['Spouse', 'Parent', 'Friend', 'Sibling'],required=True, allow_blank=False)
    prefrence = serializers.ChoiceField(choices=['Adventure', 'Relaxation', 'Nature', 'Explore', 'Spiritual', 'Historic'],required=True, allow_blank=False)

    def validate_date(self, value):
        return validate_age(value)

    def validate_phone_number(self, value):
        cleaned = validate_phone_format(value)
        if Profile.objects.filter(phone_number=cleaned).exists():
            raise serializers.ValidationError("This phone number is already registered")
        return cleaned

    def validate_enumber(self, value):
        if value:
            return validate_phone_format(value)
        return value

    def validate(self, data):
        phone_number = data.get('phone_number')
        enumber = data.get('enumber')
        if phone_number and enumber and phone_number == enumber:
            raise serializers.ValidationError({"enumber": "Emergency contact number cannot be the same as your phone number"})
        return data

class OTPVerificationSerializer(serializers.Serializer):
    otp_code = serializers.CharField(max_length=6, min_length=6)

    def validate_otp_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits")
        return value

class ProfileUpdateSerializer(serializers.ModelSerializer):
    profile_pic = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Profile
        fields = [
            'fname', 'lname', 'date', 'gender', 'bio', 'profile_pic',
            'bgroup', 'allergies', 'medical', 'ename', 'enumber', 'erelation', 'prefrence'
        ]

    def validate_date(self, value):
        if not value:
            return value
        return validate_age(value)

    def validate_profile_pic(self, value):
        if not value:
            return value
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Max file size is 5MB")
        if value.name.split('.')[-1].lower() not in ['jpg', 'jpeg', 'png', 'webp']:
            raise serializers.ValidationError("Allowed formats: jpg, jpeg, png, webp")
        return value

    def validate_enumber(self, value):
        if value:
            cleaned = re.sub(r'[^\d+]', '', value)
            if not re.match(r'^\+[1-9]\d{1,14}$', cleaned):
                raise serializers.ValidationError("Emergency number must be in international format")
            return cleaned
        return value

    def validate(self, data):
        enumber = data.get('enumber')
        if enumber and self.instance:
            if self.instance.phone_number == enumber:
                raise serializers.ValidationError({"enumber": "Emergency contact number cannot be the same as your phone number"})
        return data

class ResendOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=17)

class EmergencySOSSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=500, required=False,help_text="Optional custom emergency message")
    location = serializers.CharField(max_length=500, required=False,help_text="Optional location details")

class UserListSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='user.id', read_only=True)

    class Meta:
        model = Profile
        fields = ['id', 'fname', 'lname']
        read_only_fields = ['id', 'fname', 'lname']

class UserProfileSearchSerializer(serializers.Serializer):
    fname = serializers.CharField(max_length=100, required=True)
    lname = serializers.CharField(max_length=100, required=True)

    def validate(self, data):
        fname = data.get('fname', '').strip()
        lname = data.get('lname', '').strip()
        if not fname or not lname:
            raise serializers.ValidationError("Both first name and last name are required")
        return data

class UserProfilePublicSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='user.id', read_only=True)
    profile_pic_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = ['id', 'fname', 'lname', 'bio', 'gender', 'prefrence', 'profile_pic_url']
        read_only_fields = fields

    def get_profile_pic_url(self, obj):
       return get_s3_url(obj.profile_pic)

class UserProfileDetailSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    profile_pic_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'id', 'email', 'fname', 'lname', 'phone_number', 'date',
            'gender', 'bio', 'profile_pic_url', 'bgroup', 'allergies',
            'medical', 'ename', 'enumber', 'erelation', 'prefrence'
        ]
        read_only_fields = fields

    def get_profile_pic_url(self, obj):
       return get_s3_url(obj.profile_pic)