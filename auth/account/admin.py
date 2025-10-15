from django.contrib import admin
from account.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

class UserModelAdmin(BaseUserAdmin):
    list_display = ["id", "email", "is_email_verified", "is_admin", "created_at"]
    list_filter = ["is_admin", "is_active", "is_email_verified", "created_at"]
    
    fieldsets = [
        ('Authentication', {"fields": ["email", "password"]}),
        ("Permissions", {"fields": ["is_admin", "is_active", "is_email_verified"]}),
        ("OTP Information", {"fields": ["otp", "otp_exp", "otp_verified", "otp_type"]}),
        ("Important Dates", {"fields": ["created_at", "updated_at", "last_login"]})]
    
    add_fieldsets = [
        (None, {"classes": ["wide"], "fields": ["email", "password1", "password2"]})]
    
    readonly_fields = ["created_at", "updated_at", "last_login", "otp", "otp_exp", "otp_verified", "otp_type"]

    search_fields = ["email"]
    ordering = ["-created_at"]
    filter_horizontal = []
    
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ["email"]
        return self.readonly_fields


admin.site.register(User, UserModelAdmin)
admin.site.site_header = "TripSync Admin"
admin.site.site_title = "TripSync Admin Portal"
admin.site.index_title = "Welcome To Admin Portal"