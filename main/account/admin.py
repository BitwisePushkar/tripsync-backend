from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from account.models import User, UserSocialAccount

@admin.register(User)
class UserModelAdmin(BaseUserAdmin):
    list_display = ["id", "email", "username", "is_email_verified", "is_active", "is_admin", "created_at"]
    list_filter = ["is_admin", "is_active", "is_email_verified", "created_at"]
    search_fields = ["email", "username"]
    ordering = ["-created_at"]
    filter_horizontal = []
    fieldsets = [
        ("Identity", {"fields": ["email", "username", "password"]}),
        ("Permissions", {"fields": ["is_admin", "is_active", "is_email_verified"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at", "last_login"]}),
    ]
    add_fieldsets = [
        (None, {
            "classes": ["wide"],
            "fields": ["email", "username", "password1", "password2"],
        })
    ]

    readonly_fields = ["created_at", "updated_at", "last_login"]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ["email"]
        return self.readonly_fields
    
@admin.register(UserSocialAccount)
class UserSocialAccountAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "provider", "provider_uid", "created_at"]
    list_filter = ["provider", "created_at"]
    search_fields  = ["user__email", "user__username", "provider_uid"]
    ordering = ["-created_at"]
    raw_id_fields  = ["user"]
    readonly_fields = ["user", "provider", "provider_uid", "created_at"]
 
    def has_add_permission(self, request):
        return False
 
    def has_change_permission(self, request, obj=None):
        return False

admin.site.site_header = "TripSync Admin"
admin.site.site_title = "TripSync Admin Portal"
admin.site.index_title = "Welcome to TripSync Admin"