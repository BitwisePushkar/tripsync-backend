from rest_framework import serializers
from account.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
import re

email_regex = RegexValidator(
    regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    message="Enter a valid email address")

class UserRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True, validators=[email_regex])
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password], style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email=value, is_email_verified=True).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters.")
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter.")
        if not re.search(r'[0-9]', value):
            raise serializers.ValidationError("Password must contain at least one number.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError("Password must contain at least one special character.")
        return value

    def validate(self, data):
        if data.get('password') != data.get('password2'):
            raise serializers.ValidationError({"password2": "Passwords don't match"})
        return data

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True, validators=[email_regex])
    otp = serializers.CharField(max_length=6, min_length=6, required=True)

    def validate_email(self, value):
        return value.lower()

class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=255, required=True, validators=[email_regex])
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    def validate_email(self, value):
        return value.lower()

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "is_email_verified", "created_at"]
        read_only_fields = ["id", "email", "is_email_verified", "created_at"]

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True, validators=[email_regex])
    
    def validate_email(self, value):
        return value.lower()

class PasswordResetVerifySerializer(serializers.Serializer):
    email = serializers.EmailField(required=True, validators=[email_regex])
    otp = serializers.CharField(max_length=6, min_length=6, required=True)
    new_password = serializers.CharField(write_only=True, required=True, validators=[validate_password], style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    
    def validate_email(self, value):
        return value.lower()
    
    def validate_new_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters.")
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter.")
        if not re.search(r'[0-9]', value):
            raise serializers.ValidationError("Password must contain at least one number.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError("Password must contain at least one special character.")
        return value
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return data