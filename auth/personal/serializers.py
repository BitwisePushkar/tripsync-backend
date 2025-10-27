from rest_framework import serializers
from .models import Profile
from django.contrib.auth import get_user_model
import re

User = get_user_model()

class ProfileSerializer(serializers.ModelSerializer):
    profile_pic_url = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    class Meta:
        model = Profile
        fields = ['id', 'email', 'name', 'age', 'gender', 'location', 'phone_number', 'is_phone_verified', 'bio', 'profile_pic', 'profile_pic_url', 'created_at', 'updated_at']
        read_only_fields = ['id', 'email', 'is_phone_verified', 'created_at', 'updated_at']
    
    def get_profile_pic_url(self, obj):
        if obj.profile_pic:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_pic.url)
            return obj.profile_pic.url
        return None
    
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

    def validate_age(self, value):
        if value < 13:
            raise serializers.ValidationError("You must be at least 13 years old")
        if value > 120:
            raise serializers.ValidationError("Please enter a valid age")
        return value
    
    def validate_profile_pic(self, value):
        if value:
            if value.size > 5 * 1024 * 1024:
                raise serializers.ValidationError("Profile picture size must be less than 5MB")
            allowed_extensions = ['jpg', 'jpeg', 'png', 'webp']
            ext = value.name.split('.')[-1].lower()
            if ext not in allowed_extensions:
                raise serializers.ValidationError(
                    f"Unsupported file format. Allowed formats: {', '.join(allowed_extensions)}"
                )
        return value

class PersonalDetailsInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    age = serializers.IntegerField(min_value=13, max_value=120)
    gender = serializers.ChoiceField(choices=['male', 'female', 'other', 'none'],required=False,allow_blank=True)
    location = serializers.CharField(max_length=200)
    phone_number = serializers.CharField(max_length=17)
    bio = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_phone_number(self, value):
        cleaned = re.sub(r'[^\d+]', '', value)
        if not re.match(r'^\+[1-9]\d{1,14}$', cleaned):
            raise serializers.ValidationError("Phone number must be in international format (e.g., +1234567890)")
        if Profile.objects.filter(phone_number=cleaned).exists():
            raise serializers.ValidationError("This phone number is already registered")
        return cleaned

class OTPVerificationSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=17)
    otp_code = serializers.CharField(max_length=6, min_length=6)
    def validate_otp_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits")
        return value

class ProfileUpdateSerializer(serializers.ModelSerializer):
    profile_pic = serializers.ImageField(required=False, allow_null=True)
    class Meta:
        model = Profile
        fields = ['name', 'age', 'gender', 'location', 'bio', 'profile_pic']
    
    def validate_profile_pic(self, value):
        if not value:
            return value
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Max file size is 5MB")
        if value.name.split('.')[-1].lower() not in ['jpg', 'jpeg', 'png', 'webp']:
            raise serializers.ValidationError("Allowed formats: jpg, jpeg, png, webp")
        return value

class ResendOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=17)