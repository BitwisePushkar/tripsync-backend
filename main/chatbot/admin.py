from django.contrib import admin
from .models import ChatMessage

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display  = ('session_id', 'user', 'short_message', 'created_at')
    list_filter   = ('created_at',)
    search_fields = ('session_id', 'user_message', 'bot_response')
    readonly_fields = ('session_id', 'user', 'user_message', 'bot_response', 'created_at')
    ordering = ('-created_at',)

    def short_message(self, obj):
        return obj.user_message[:80]
    short_message.short_description = 'User Message'