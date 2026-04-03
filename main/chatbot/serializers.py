from rest_framework import serializers
from .models import ChatMessage

class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(required=True,max_length=5000,)
    session_id = serializers.CharField(required=False,max_length=100,allow_blank=False,)

    def validate_message(self, value):
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("Message cannot be empty or whitespace.")
        return stripped

    def validate_session_id(self, value):
        return value.strip() if value else value

class ChatResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField(help_text="The user's original message")
    response = serializers.CharField(help_text="WanderBot's reply")
    session_id = serializers.CharField(help_text="Use this in subsequent requests to maintain conversation context")
    created_at = serializers.DateTimeField()

class ChatHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'user_message', 'bot_response', 'created_at']
        read_only_fields = fields

class HistoryResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    session_id = serializers.CharField()
    count = serializers.IntegerField(help_text="Total number of messages in this session")
    messages = ChatHistorySerializer(many=True)