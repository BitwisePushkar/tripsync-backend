from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from django.db.models import Count, Q
from account.models import User
from .models import Conversation, Message
from .serializers import (ConversationSerializer, MessageSerializer, CreateMessageSerializer,CreateConversationSerializer,ConversationDetailSerializer)

class ConversationListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateConversationSerializer
        return ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(
            participants=self.request.user
        ).prefetch_related('participants', 'messages').annotate(
            message_count=Count('messages')
        ).order_by('-updated_at')

    @extend_schema(
        summary="List user's conversations",
        description="Get all conversations where the authenticated user is a participant, ordered by most recent activity",
        responses={
            200: ConversationSerializer(many=True),
            401: OpenApiTypes.OBJECT,
        },
        tags=['Chat - Conversations']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Create a conversation",
        description="Create a new conversation (DM or group). For DM between 2 users, returns existing conversation if it already exists.",
        request=CreateConversationSerializer,
        examples=[
            OpenApiExample(
                'Direct Message',
                value={
                    'participant_ids': [2], 
                },
                request_only=True,
            ),
            OpenApiExample(
                'Group Chat',
                value={
                    'participant_ids': [2, 3, 4],
                    'name': 'Trip Planning Group'
                },
                request_only=True,
            ),
        ],
        responses={
            201: ConversationSerializer,
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
        },
        tags=['Chat - Conversations']
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = serializer.save()
        response_serializer = ConversationSerializer(
            conversation, 
            context={'request': request}
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

class ConversationDetailView(generics.RetrieveDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ConversationDetailSerializer

    def get_queryset(self):
        return Conversation.objects.filter(participants=self.request.user)
    @extend_schema(
        summary="Get conversation details",
        description="Get detailed information about a conversation including participants and recent messages",
        responses={
            200: ConversationDetailSerializer,
            401: OpenApiTypes.OBJECT,
            403: "Forbidden - Not a participant",
            404: "Not Found",
        },
        tags=['Chat - Conversations']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Leave conversation",
        description="Remove yourself from a conversation. If you're the last participant, the conversation will be deleted.",
        responses={
            204: "Successfully left conversation",
            401: OpenApiTypes.OBJECT,
            403: "Forbidden - Not a participant",
            404: "Not Found",
        },
        tags=['Chat - Conversations']
    )
    def delete(self, request, *args, **kwargs):
        conversation = self.get_object()
        conversation.participants.remove(request.user)
        if conversation.participants.count() == 0:
            conversation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        conversation_id = self.kwargs['conversation_id']
        conversation = self.get_conversation(conversation_id)
        return Message.objects.filter(
            conversation=conversation
        ).select_related('sender').order_by('timestamp')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateMessageSerializer
        return MessageSerializer

    @extend_schema(
        summary="List messages",
        description="Get all messages from a conversation. User must be a participant.",
        parameters=[
            OpenApiParameter(
                name='conversation_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Conversation ID',
                required=True
            )
        ],
        responses={
            200: MessageSerializer(many=True),
            401: OpenApiTypes.OBJECT,
            403: "Forbidden - Not a participant",
            404: "Not Found",
        },
        tags=['Chat - Messages']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Send message",
        description="Send a new message to the conversation. User must be a participant.",
        parameters=[
            OpenApiParameter(
                name='conversation_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Conversation ID',
                required=True
            )
        ],
        request=CreateMessageSerializer,
        examples=[
            OpenApiExample(
                'Text Message',
                value={'content': 'What time should we meet for the trip?'},
                request_only=True,
            ),
        ],
        responses={
            201: MessageSerializer,
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
            403: "Forbidden - Not a participant",
            404: "Not Found",
        },
        tags=['Chat - Messages']
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        conversation_id = self.kwargs['conversation_id']
        conversation = self.get_conversation(conversation_id)
        serializer.save(sender=self.request.user, conversation=conversation)

    def get_conversation(self, conversation_id):
        conversation = get_object_or_404(Conversation, id=conversation_id)
        if not conversation.is_participant(self.request.user):
            raise PermissionDenied('You are not a participant of this conversation')
        return conversation

class MessageRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer

    def get_queryset(self):
        conversation_id = self.kwargs['conversation_id']
        conversation = get_object_or_404(Conversation, id=conversation_id)
        if not conversation.is_participant(self.request.user):
            raise PermissionDenied('You are not a participant of this conversation')
        
        return Message.objects.filter(conversation=conversation)

    @extend_schema(
        summary="Get message details",
        description="Retrieve a specific message from a conversation",
        parameters=[
            OpenApiParameter(
                name='conversation_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Conversation ID',
                required=True
            ),
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Message ID',
                required=True
            )
        ],
        responses={
            200: MessageSerializer,
            401: OpenApiTypes.OBJECT,
            403: "Forbidden - Not a participant",
            404: "Not Found",
        },
        tags=['Chat - Messages']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Edit message",
        description="Edit your own message content. Only the sender can edit their messages.",
        parameters=[
            OpenApiParameter(
                name='conversation_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Conversation ID',
                required=True
            ),
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Message ID',
                required=True
            )
        ],
        request=CreateMessageSerializer,
        responses={
            200: MessageSerializer,
            401: OpenApiTypes.OBJECT,
            403: "Forbidden - Not the sender",
            404: "Not Found",
        },
        tags=['Chat - Messages']
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        summary="Delete message",
        description="Delete your own message. Only the sender can delete their messages.",
        parameters=[
            OpenApiParameter(
                name='conversation_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Conversation ID',
                required=True
            ),
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Message ID',
                required=True
            )
        ],
        responses={
            204: "Message deleted",
            401: OpenApiTypes.OBJECT,
            403: "Forbidden - Not the sender",
            404: "Not Found",
        },
        tags=['Chat - Messages']
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

    def perform_update(self, serializer):
        if serializer.instance.sender != self.request.user:
            raise PermissionDenied('You can only edit your own messages')
        
        from django.utils import timezone
        serializer.save(edited_at=timezone.now())

    def perform_destroy(self, instance):
        if instance.sender != self.request.user:
            raise PermissionDenied('You can only delete your own messages')
        instance.delete()