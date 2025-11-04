import re
from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

def validate_strong_password(value: str) -> str:
    errors = []
    if len(value) < 8:
        errors.append("Password must be at least 8 characters.")
    if not re.search(r"[A-Z]", value):
        errors.append("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", value):
        errors.append("Password must contain at least one lowercase letter.")
    if not re.search(r"[0-9]", value):
        errors.append("Password must contain at least one digit.")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
        errors.append("Password must contain at least one special character.")
    if errors:
        raise serializers.ValidationError(errors)
    return value

def validate_username(value: str) -> str:
    value = value.strip().lower()
    if len(value) < 5:
        raise serializers.ValidationError("Username must be at least 5 characters.")
    if len(value) > 15:
        raise serializers.ValidationError("Username cannot exceed 15 characters.")
    if not re.match(r"^[a-zA-Z0-9_@#]+$", value):
        raise serializers.ValidationError("Username may only contain letters, numbers, underscores, @, and #.")
    if value.isdigit():
        raise serializers.ValidationError("Username cannot be entirely numeric.")
    return value

class UserRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    username = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"},)
    password2 = serializers.CharField(write_only=True, required=True, style={"input_type": "password"},)

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if User.objects.filter(email=value, is_email_verified=True).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_username(self, value: str) -> str:
        value = validate_username(value)
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_password(self, value: str) -> str:
        return validate_strong_password(value)

    def validate(self, data: dict) -> dict:
        if data.get("password") != data.get("password2"):
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        return data

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=6, max_length=6,)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate_otp(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError("OTP must be a 6-digit number.")
        return value

class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

class UserLoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=True, help_text="Your email address or username.",)
    password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"},)

    def validate_identifier(self, value: str) -> str:
        return value.strip().lower()

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

class PasswordResetVerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate_otp(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError("OTP must be a 6-digit number.")
        return value

class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    reset_token = serializers.CharField(required=True)
    new_password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"},)
    confirm_password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"},)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate_new_password(self, value: str) -> str:
        return validate_strong_password(value)

    def validate(self, data: dict) -> dict:
        if data.get("new_password") != data.get("confirm_password"):
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return data