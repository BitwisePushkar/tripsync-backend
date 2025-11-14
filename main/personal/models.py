from django.db import models
from django.conf import settings

LANGUAGE_CHOICES = [
    ("en", "English"),
    ("hi", "Hindi"),
    ("ar", "Arabic"),
    ("fr", "French"),
    ("es", "Spanish"),
]

PREFERENCE_CHOICES = [
    ("relaxed", "Relaxed"),
    ("adventurous", "Adventurous"),
    ("nature", "Nature"),
    ("cultural", "Cultural"),
    ("spiritual", "Spiritual"),
    ("historic", "Historic"),
]

GENDER_CHOICES = [
    ("male", "Male"),
    ("female", "Female"),
    ("other", "Other"),
]

BLOOD_GROUP_CHOICES = [
    ("A+", "A+"), ("A-", "A-"),
    ("B+", "B+"), ("B-", "B-"),
    ("AB+", "AB+"), ("AB-", "AB-"),
    ("O+", "O+"), ("O-", "O-"),
]

RELATION_CHOICES = [
    ("Spouse", "Spouse"),
    ("Parent", "Parent"),
    ("Friend", "Friend"),
    ("Sibling", "Sibling"),
    ("Other", "Other"),
]

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile",)
    fname = models.CharField(max_length=100, verbose_name="First name",)
    lname = models.CharField(max_length=100, blank=True, default="", verbose_name="Last name",)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, verbose_name="Gender",)
    date_of_birth = models.DateField(verbose_name="Date of birth", help_text="Must be between 13 and 110 years old.",)
    bio = models.TextField(max_length=500, blank=True, default="", verbose_name="Bio",)
    profile_pic = models.CharField(max_length=500, blank=True, default="", verbose_name="Profile picture URL",)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, verbose_name="Blood group",)
    allergies = models.TextField(max_length=300, verbose_name="Allergies",)
    medical = models.TextField(max_length=500, verbose_name="Medical conditions",)
    preference = models.CharField(max_length=20, choices=PREFERENCE_CHOICES, verbose_name="Trip preference",)
    preferred_destinations = models.JSONField(default=list, verbose_name="Preferred destinations",)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="en", verbose_name="Language preference",)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Profile"
        verbose_name_plural = "Profiles"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.fname} {self.lname}".strip() or f"Profile({self.user.email})"

    @property
    def full_name(self) -> str:
        return f"{self.fname} {self.lname}".strip()

class EmergencyContact(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="emergency_contacts",)
    name = models.CharField(max_length=100, verbose_name="Contact name",)
    phone_number = models.CharField(max_length=17, verbose_name="Phone number", help_text="International format e.g. +911234567890.",)
    email = models.EmailField(verbose_name="Email address", help_text="Emergency alert emails are sent here.",)
    relation = models.CharField(max_length=10, choices=RELATION_CHOICES, verbose_name="Relation",)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Emergency Contact"
        verbose_name_plural = "Emergency Contacts"
        ordering = ["created_at"] 
        
    def __str__(self):
        return f"{self.name} ({self.relation}) for {self.profile}"