from rest_framework import serializers
from account.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from django.utils import timezone
import re

email_regex = RegexValidator(
    regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    message="Enter a valid email address"
)

phone_regex = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
)

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'},
        help_text="Password must contain at least 8 characters, including uppercase, lowercase, numbers, and special characters"
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text="Confirm your password"
    )
    email = serializers.EmailField(
        required=True,
        validators=[email_regex],
        help_text="Enter a valid email address"
    )
    phone_number = serializers.CharField(
        required=True,
        validators=[phone_regex],
        help_text="Format: '+919999999999' or '9999999999'"
    )
    terms_accepted = serializers.BooleanField(
        required=True,
        help_text="You must accept terms and conditions"
    )

    class Meta:
        model = User
        fields = ["email", "name", "terms_accepted", "phone_number", "password", "password2"]
        extra_kwargs = {
            'name': {'required': True, 'help_text': 'Enter your full name'}
        }

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_phone_number(self, value):
        cleaned_phone = re.sub(r'[\s-]', '', value)
        if User.objects.filter(phone_number=cleaned_phone).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        return cleaned_phone

    def validate_terms_accepted(self, value):
        if not value:
            raise serializers.ValidationError("You must accept the terms and conditions to register.")
        return value

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
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
            raise serializers.ValidationError({
                "password2": "Password and confirm password don't match"
            })
        return data

    def create(self, validated_data):
        validated_data.pop('password2', None)
        user = User.objects.create_user(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(
        max_length=255,
        required=True,
        validators=[email_regex],
        help_text="Enter your registered email"
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text="Enter your password"
    )

    def validate_email(self, value):
        return value.lower()


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name", "phone_number", "is_email_verified", "created_at"]
        read_only_fields = ["id", "email", "is_email_verified", "created_at"]


class UserListSerializer(serializers.ModelSerializer):
    days_since_joined = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "name", "phone_number", "is_email_verified",
            "is_active", "created_at", "days_since_joined"
        ]
        read_only_fields = ["id", "email", "is_email_verified", "created_at"]

    def get_days_since_joined(self, obj):
        delta = timezone.now() - obj.created_at
        return delta.days


class VerifyEmailOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True,
        validators=[email_regex],
        help_text="Your email address"
    )
    otp = serializers.CharField(
        max_length=6,
        min_length=6,
        required=True,
        help_text="6-digit OTP code"
    )
    
    def validate_email(self, value):
        return value.lower()
    
    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits.")
        return value
    
    def validate(self, data):
        try:
            user = User.objects.get(email=data['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "Invalid request."})
        
        if user.is_email_verified:
            raise serializers.ValidationError({"email": "Email is already verified."})
        
        # Check if OTP exists and not expired - validation happens in view with attempt tracking
        if not user.otp or not user.otp_exp:
            raise serializers.ValidationError({"otp": "No OTP found. Please request a new one."})
        
        data['user'] = user
        return data


class PasswordResetVerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True,
        validators=[email_regex],
        help_text="Your email address"
    )
    otp = serializers.CharField(
        max_length=6,
        min_length=6,
        required=True,
        help_text="6-digit OTP code"
    )
    
    def validate_email(self, value):
        return value.lower()
    
    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits.")
        return value
    
    def validate(self, data):
        try:
            user = User.objects.get(email=data['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "Invalid request."})
        
        if not user.otp or not user.otp_exp:
            raise serializers.ValidationError({"otp": "No OTP found. Please request password reset first."})
        
        data['user'] = user
        return data


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True,
        validators=[email_regex],
        help_text="Your email address"
    )
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'},
        help_text="Enter your new password"
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text="Confirm your new password"
    )
    
    def validate_email(self, value):
        return value.lower()
    
    def validate_new_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
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
        try:
            user = User.objects.get(email=data['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "Invalid request."})
        
        if not user.otp_verified:
            raise serializers.ValidationError({"otp": "OTP verification required. Please verify OTP first."})
        
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        
        data['user'] = user
        return data