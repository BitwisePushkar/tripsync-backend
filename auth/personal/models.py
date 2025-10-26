from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from datetime import timedelta
import random
import hashlib

def validate_image_size(image):
    file_size = image.size
    limit_mb = 5
    if file_size > limit_mb * 1024 * 1024:
        raise ValidationError(f"Max file size is {limit_mb}MB")

class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='profile'
    )
    name = models.CharField(max_length=100)
    age = models.PositiveIntegerField()
    gender = models.CharField(
        max_length=10,
        choices=[
            ('male', 'Male'), 
            ('female', 'Female'), 
            ('other', 'Other'),
            ('none', 'Prefer not to say')
        ],
        blank=True
    )
    location = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=17, unique=True)
    is_phone_verified = models.BooleanField(default=False)
    bio = models.TextField(max_length=500, blank=True)
    profile_pic = models.ImageField(
        upload_to='profile_pics/', 
        blank=True, 
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp']),
            validate_image_size
        ],
        help_text="Upload profile picture (max 5MB, formats: jpg, jpeg, png, webp)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    otp = models.CharField(max_length=255, blank=True, null=True)
    otp_exp = models.DateTimeField(blank=True, null=True)
    otp_attempts = models.IntegerField(default=0)
    otp_locked_until = models.DateTimeField(blank=True, null=True)

    def _hash_otp(self, otp_code):
        return hashlib.sha256(otp_code.encode()).hexdigest()
    
    def generate_otp(self):
        otp_code = str(random.randint(100000, 999999))
        self.otp = self._hash_otp(otp_code)
        self.otp_exp = timezone.now() + timedelta(minutes=getattr(settings, 'OTP_EXPIRY_MINUTES', 5))
        self.otp_attempts = 0
        self.save()
        return otp_code  
    
    def is_otp_locked(self):
        if self.otp_locked_until and self.otp_locked_until > timezone.now():
            return True
        return False
    
    def verify_otp(self, otp_code):
        if self.is_otp_locked():
            time_remaining = (self.otp_locked_until - timezone.now()).seconds // 60
            return False, f"Too many failed attempts. Try again in {time_remaining} minutes.", 0
        if not self.otp or not self.otp_exp:
            return False, "No OTP found. Please request a new one.", 0
        if self.otp_exp < timezone.now():
            self.clear_otp()  # Clear expired OTP
            return False, "OTP has expired. Please request a new one.", 0
        
        hashed_input = self._hash_otp(otp_code)
        max_attempts = getattr(settings, 'MAX_OTP_ATTEMPTS', 3)
        
        if self.otp == hashed_input:
            self.is_phone_verified = True
            self.clear_otp() 
            return True, "OTP verified successfully!", max_attempts
        else:
            self.otp_attempts += 1
            attempts_remaining = max_attempts - self.otp_attempts
            
            if self.otp_attempts >= max_attempts:
                lockout_minutes = getattr(settings, 'OTP_LOCKOUT_MINUTES', 15)
                self.otp_locked_until = timezone.now() + timedelta(minutes=lockout_minutes)
                self.clear_otp() 
                self.save()
                return False, f"Too many failed attempts. Account locked for {lockout_minutes} minutes.", 0
            self.save()
            return False, f"Invalid OTP. {attempts_remaining} attempt(s) remaining.", attempts_remaining
    
    def clear_otp(self):
        self.otp = None
        self.otp_exp = None
        self.otp_attempts = 0
        self.otp_locked_until = None
        self.save()
    
    def __str__(self):
        return f"{self.name}'s Profile"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number']),
            models.Index(fields=['is_phone_verified']),
        ]