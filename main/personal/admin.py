from django.contrib import admin
from .models import Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'fname', 'lname', 'phone_number', 'is_phone_verified', 'gender', 'created_at']
    list_filter = ['is_phone_verified', 'gender', 'bgroup', 'erelation', 'prefrence']
    search_fields = ['fname', 'lname', 'phone_number', 'user__email']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'last_otp_sent_at','otp', 'otp_exp', 'otp_attempts', 'otp_locked_until']
    fieldsets = [
        ('User', {'fields': ['user']}),
        ('Personal Info', {'fields': ['fname', 'lname', 'date', 'gender', 'bio', 'profile_pic']}),
        ('Contact', {'fields': ['phone_number', 'is_phone_verified']}),
        ('Medical', {'fields': ['bgroup', 'allergies', 'medical']}),
        ('Emergency Contact', {'fields': ['ename', 'enumber', 'erelation']}),
        ('Preferences', {'fields': ['prefrence']}),
        ('OTP (read-only)', {'fields': ['otp', 'otp_exp', 'otp_attempts', 'otp_locked_until', 'last_otp_sent_at']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at']}),
    ]