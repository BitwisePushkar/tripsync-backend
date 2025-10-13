from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser
from django.core.validators import RegexValidator
from django.utils import timezone
from datetime import timedelta
import random
import re

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
    


    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_exp = models.DateTimeField(blank=True, null=True)
    otp_verified = models.BooleanField(default=False)
    

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
    


    def generate_otp(self):
        self.otp = str(random.randint(100000, 999999))
        self.otp_exp = timezone.now() + timedelta(minutes=10)
        self.otp_verified = False
        self.save()
        return self.otp
    
    def verify_otp(self, otp_code):
        if self.otp == otp_code and self.otp_exp and self.otp_exp > timezone.now():
            self.otp_verified = True
            self.is_email_verified = True
            self.save()
            return True
        return False
    
    def clear_otp(self):
        self.otp = None
        self.otp_exp = None
        self.otp_verified = False
        self.save()
    

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ['-created_at']