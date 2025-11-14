from django.contrib import admin
from personal.models import Profile, EmergencyContact

class EmergencyContactInline(admin.TabularInline):
    model = EmergencyContact
    extra = 0 
    max_num = 3
    min_num = 0
    fields = ["name", "phone_number", "email", "relation", "created_at"]
    readonly_fields = ["created_at"]
    can_delete = True
    show_change_link = False

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = [
        "id", "full_name", "user_email", "gender",
        "blood_group", "preference", "language", "created_at",
    ]
    list_filter = ["gender", "blood_group", "preference", "language", "created_at"]
    search_fields = ["fname", "lname", "user__email"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [EmergencyContactInline]
    fieldsets = [
        ("User", {"fields": ["user"]}),
        ("Personal", {"fields": ["fname", "lname", "gender", "date_of_birth", "bio", "profile_pic"]}),
        ("Medical", {"fields": ["blood_group", "allergies", "medical"]}),
        ("Preferences", {"fields": ["preference", "preferred_destinations", "language"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    ]

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "Email"
    user_email.admin_order_field = "user__email"
    
    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = "Name"
    full_name.admin_order_field = "fname"

@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "email", "phone_number", "relation", "profile_owner", "created_at"]
    list_filter = ["relation", "created_at"]
    search_fields = ["name", "email", "phone_number", "profile__user__email"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["profile"]

    def profile_owner(self, obj):
        return obj.profile.user.email
    profile_owner.short_description = "Profile owner"
    profile_owner.admin_order_field = "profile__user__email"