from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser
from django.core.validators import RegexValidator
import re

phone_regex = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
)

class UserManager(BaseUserManager):
    def create_user(self, email, name, phone_number, password=None, password2=None, terms_accepted=False):
        """
        Creates and saves a User with the given email, name, phone_number and password.
        """
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
        """
        Creates and saves a superuser with the given email, name, phone_number and password.
        """
        user = self.create_user(
            email=email,
            password=password,
            name=name,
            phone_number=phone_number,
            terms_accepted=True,
        )
        user.is_admin = True
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
        help_text="User must accept terms and conditions"
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

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ['name', 'phone_number']

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        "Does the user have a specific permission?"
        return self.is_admin

    def has_module_perms(self, app_label):
        "Does the user have permissions to view the app `app_label`?"
        return True

    @property
    def is_staff(self):
        "Is the user a member of staff?"
        return self.is_admin
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ['-created_at']