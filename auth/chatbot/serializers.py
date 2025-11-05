from rest_framework import serializers
from .models import ChatMessage

class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(required=True, max_length=5000, help_text="User message to send to the chatbot")
    system_prompt = serializers.CharField(required=False, default='You are a helpful AI assistant.', max_length=2000, help_text="Custom system prompt for the chatbot")
    session_id = serializers.CharField(required=False, max_length=100, help_text="Session ID for conversation continuity")

    def validate_message(self, value):
        if not value.strip():
            raise serializers.ValidationError("Message cannot be empty")
        return value.strip()


class ChatResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True)
    message = serializers.CharField()
    response = serializers.CharField()
    session_id = serializers.CharField()
    created_at = serializers.DateTimeField()


class ChatHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'user_message', 'bot_response', 'created_at']
        read_only_fields = ['id', 'user_message', 'bot_response', 'created_at']


class HistoryResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True)
    session_id = serializers.CharField()
    count = serializers.IntegerField()
    messages = ChatHistorySerializer(many=True)