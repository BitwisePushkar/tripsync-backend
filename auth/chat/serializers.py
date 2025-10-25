from rest_framework import serializers
from account.models import User
from .models import Conversation, Message
from django.db import models  
from django.db.models import Count, Q


class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email')  
        read_only_fields = ('id', 'email')

class MessageSerializer(serializers.ModelSerializer):
    sender = UserListSerializer(read_only=True)
    
    class Meta:
        model = Message
        fields = ('id', 'conversation', 'sender', 'content', 'timestamp', 'is_read', 'edited_at')
        read_only_fields = ('id', 'sender', 'timestamp', 'conversation', 'is_read', 'edited_at')

class CreateMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ('content',)
    
    def validate_content(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Message content cannot be empty")
        if len(value) > 5000:
            raise serializers.ValidationError("Message too long (max 5000 characters)")
        return value.strip()

class ConversationSerializer(serializers.ModelSerializer):
    participants = UserListSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = (
            'id', 
            'name', 
            'is_group', 
            'participants', 
            'created_at', 
            'updated_at',
            'last_message',
            'unread_count'
        )
        read_only_fields = ('id', 'created_at', 'updated_at', 'is_group')

    def get_last_message(self, obj):
        last_msg = obj.messages.order_by('-timestamp').first()
        if last_msg:
            return {
                'id': last_msg.id,
                'content': last_msg.content[:100], 
                'sender': UserListSerializer(last_msg.sender).data,
                'timestamp': last_msg.timestamp
            }
        return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.messages.filter(is_read=False).exclude(sender=request.user).count()
        return 0


class ConversationDetailSerializer(serializers.ModelSerializer):
    participants = UserListSerializer(many=True, read_only=True)
    messages = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = ('id', 'name', 'is_group', 'participants', 'created_at', 'messages')
        read_only_fields = ('id', 'created_at', 'is_group')
    
    def get_messages(self, obj):
        messages = obj.messages.order_by('-timestamp')[:50]
        return MessageSerializer(messages, many=True).data


class CreateConversationSerializer(serializers.Serializer):
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=50,
        help_text="List of user IDs to add to conversation"
    )
    name = serializers.CharField(
        max_length=255, 
        required=False, 
        allow_blank=True,
        help_text="Optional name for group conversations"
    )
    
    def validate_participant_ids(self, value):
        unique_ids = list(set(value))
        existing_users = User.objects.filter(id__in=unique_ids).count()
        if existing_users != len(unique_ids):
            raise serializers.ValidationError("One or more users do not exist")
        return unique_ids
    
    def create(self, validated_data):
        participant_ids = validated_data.pop('participant_ids')
        name = validated_data.get('name', '')
        request_user = self.context['request'].user
        if request_user.id not in participant_ids:
            participant_ids.append(request_user.id)
        if len(participant_ids) == 2:
            existing_conv = Conversation.objects.filter(
            participants__id=participant_ids[0]).filter(
            participants__id=participant_ids[1]).annotate(
            participant_count=Count('participants')).filter(
            participant_count=2).first()
        
        if existing_conv:
            return existing_conv
        
        conversation = Conversation.objects.create(name=name,is_group=(len(participant_ids) > 2))
        conversation.participants.set(participant_ids)
        return conversation