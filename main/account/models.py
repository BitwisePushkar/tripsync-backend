from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser
import re

class UserManager(BaseUserManager):
    def create_user(self, email: str, username: str, password: str = None):
        if not email:
            raise ValueError("Users must have an email address.")
        if not username:
            raise ValueError("Users must have a username.")
        user = self.model(email=self.normalize_email(email).lower(), username=username.lower(),)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, username: str, password: str = None):
        user = self.create_user(email=email, username=username, password=password)
        user.is_admin = True
        user.is_email_verified = True
        user.save(using=self._db)
        return user

class User(AbstractBaseUser):
    email = models.EmailField(verbose_name="Email address", max_length=255, unique=True, db_index=True,)
    username = models.CharField(verbose_name="Username", max_length=15, unique=True, db_index=True,)
    is_active = models.BooleanField(default=True,)
    is_admin = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False,)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]  

    def has_perm(self, perm, obj=None):
        return self.is_admin

    def has_module_perms(self, app_label):
        return True

    @property
    def is_staff(self):
        return self.is_admin

    def __str__(self):
        return f"{self.username} <{self.email}>"

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-created_at"]