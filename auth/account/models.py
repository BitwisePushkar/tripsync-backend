from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser
from django.core.validators import RegexValidator
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import random
import hashlib

phone_regex = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
)

class UserManager(BaseUserManager):
    def create_user(self, email, name, phone_number, password=None, password2=None, terms_accepted=False):
        if not email:
            raise ValueError("Users must have an email address")
        if not phone_number:
            raise ValueError("Users must have a phone number")
        
        user = self.model(
            email=self.normalize_email(email),
            name=name,
            phone_number=phone_number,
            terms_accepted=terms_accepted,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, name, phone_number, password=None):
        user = self.create_user(
            email=email,
            password=password,
            name=name,
            phone_number=phone_number,
            terms_accepted=True,
        )
        user.is_admin = True
        user.is_email_verified = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    email = models.EmailField(
        verbose_name="Email",
        max_length=255,
        unique=True,
    )
    name = models.CharField(max_length=200)
    terms_accepted = models.BooleanField(
        default=False,
        help_text="Accept the terms and conditions first"
    )
    phone_number = models.CharField(
        max_length=15,
        unique=True,
        validators=[phone_regex]
    )
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # OTP Fields with Enhanced Security
    otp = models.CharField(max_length=255, blank=True, null=True)  # Hashed OTP
    otp_exp = models.DateTimeField(blank=True, null=True)
    otp_verified = models.BooleanField(default=False)
    otp_attempts = models.IntegerField(default=0)  # Track failed attempts
    otp_locked_until = models.DateTimeField(blank=True, null=True)  # Lockout timestamp
    
    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ['name', 'phone_number']
    
    def __str__(self):
        return self.email
    
    def has_perm(self, perm, obj=None):
        return self.is_admin
    
    def has_module_perms(self, app_label):
        return True
    
    @property
    def is_staff(self):
        return self.is_admin
    
    def _hash_otp(self, otp_code):
        """Hash OTP for secure storage"""
        return hashlib.sha256(otp_code.encode()).hexdigest()
    
    def generate_otp(self):
        """Generate and store hashed OTP with expiration"""
        otp_code = str(random.randint(100000, 999999))
        self.otp = self._hash_otp(otp_code)
        self.otp_exp = timezone.now() + timedelta(
            minutes=getattr(settings, 'OTP_EXPIRY_MINUTES', 10)
        )
        self.otp_verified = False
        self.otp_attempts = 0 
        self.save()
        return otp_code
    
    def is_otp_locked(self):
        """Check if OTP verification is locked due to too many attempts"""
        if self.otp_locked_until and self.otp_locked_until > timezone.now():
            return True
        return False
    
    def verify_otp(self, otp_code):
        """
        Verify OTP with attempt tracking and lockout mechanism
        Returns: (success: bool, message: str, attempts_remaining: int)
        """
        if self.is_otp_locked():
            time_remaining = (self.otp_locked_until - timezone.now()).seconds // 60
            return False, f"Too many failed attempts. Try again in {time_remaining} minutes.", 0
        
        if not self.otp or not self.otp_exp:
            return False, "No OTP found. Please request a new one.", 0
        
        if self.otp_exp < timezone.now():
            return False, "OTP has expired. Please request a new one.", 0
        

        hashed_input = self._hash_otp(otp_code)
        max_attempts = getattr(settings, 'MAX_OTP_ATTEMPTS', 5)
        
        if self.otp == hashed_input:
            self.otp_verified = True
            self.otp_attempts = 0
            self.otp_locked_until = None
            self.save()
            return True, "OTP verified successfully!", max_attempts
        else:
            self.otp_attempts += 1
            attempts_remaining = max_attempts - self.otp_attempts
            
            if self.otp_attempts >= max_attempts:
                lockout_hours = getattr(settings, 'OTP_LOCKOUT_HOURS', 1)
                self.otp_locked_until = timezone.now() + timedelta(hours=lockout_hours)
                self.save()
                return False, f"Too many failed attempts. Account locked for {lockout_hours} hour(s).", 0
            
            self.save()
            return False, f"Invalid OTP. {attempts_remaining} attempt(s) remaining.", attempts_remaining
    
    def clear_otp(self):
        """Clear OTP data after successful verification or password reset"""
        self.otp = None
        self.otp_exp = None
        self.otp_verified = False
        self.otp_attempts = 0
        self.otp_locked_until = None
        self.save()
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ['-created_at']