from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from account.models import User
from .models import Conversation, Message
from .serializers import (
    ConversationSerializer, 
    MessageSerializer, 
    CreateMessageSerializer, 
    UserListSerializer
)

class ConversationListCreateView(generics.ListCreateAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(
            participants=self.request.user
        ).prefetch_related('participants')

    @extend_schema(
        summary="List all conversations",
        description="Retrieve all conversations where the authenticated user is a participant",
        responses={
            200: ConversationSerializer(many=True),
            401: OpenApiTypes.OBJECT,
        },
        tags=['Chat - Conversations']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Create a new conversation",
        description="Create a new conversation with multiple participants (2-50 users). The authenticated user will be automatically added if not included.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'participants': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Array of user IDs (minimum 2, maximum 50)',
                        'example': ['1', '2', '3']
                    },
                    'name': {
                        'type': 'string',
                        'description': 'Optional conversation name',
                        'example': 'Project Team Chat'
                    }
                },
                'required': ['participants']
            }
        },
        examples=[
            OpenApiExample(
                'Group Chat',
                value={
                    'participants': ['1', '2', '3'],
                    'name': 'Project Team'
                },
                request_only=True,
            ),
            OpenApiExample(
                'Direct Message',
                value={
                    'participants': ['1', '2'],
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
    def create(self, request, *args, **kwargs):
        participants_data = request.data.get('participants', [])
        
        if len(participants_data) < 2:
            return Response(
                {'error': 'A conversation needs at least two participants'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(participants_data) > 50:
            return Response(
                {'error': 'Cannot have more than 50 participants'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if str(request.user.id) not in map(str, participants_data):
            participants_data.append(str(request.user.id))
        
        users = User.objects.filter(id__in=participants_data)
        
        if users.count() != len(set(participants_data)):
            return Response(
                {'error': 'One or more participants do not exist'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        name = request.data.get('name', None)
        conversation = Conversation.objects.create(name=name)
        conversation.participants.set(users)
        serializer = self.get_serializer(conversation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MessageListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        conversation_id = self.kwargs['conversation_id']
        conversation = self.get_conversation(conversation_id)
        return conversation.messages.order_by('timestamp')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateMessageSerializer
        return MessageSerializer

    @extend_schema(
        summary="List messages in a conversation",
        description="Retrieve all messages from a specific conversation ordered by timestamp. User must be a participant of the conversation.",
        parameters=[
            OpenApiParameter(
                name='conversation_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID of the conversation',
                required=True
            )
        ],
        responses={
            200: MessageSerializer(many=True),
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        tags=['Chat - Messages']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Send a message",
        description="Create and send a new message in the conversation. User must be a participant of the conversation.",
        parameters=[
            OpenApiParameter(
                name='conversation_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID of the conversation',
                required=True
            )
        ],
        request=CreateMessageSerializer,
        examples=[
            OpenApiExample(
                'Text Message',
                value={
                    'content': 'Hello everyone! How is the project going?',
                },
                request_only=True,
            ),
        ],
        responses={
            201: MessageSerializer,
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
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
        if self.request.user not in conversation.participants.all():
            raise PermissionDenied('You are not a participant of this conversation')
        return conversation


class MessageRetrieveDestroyView(generics.RetrieveDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer

    def get_queryset(self):
        conversation_id = self.kwargs['conversation_id']
        return Message.objects.filter(conversation__id=conversation_id)

    @extend_schema(
        summary="Retrieve a specific message",
        description="Get details of a specific message by ID from a conversation",
        parameters=[
            OpenApiParameter(
                name='conversation_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID of the conversation',
                required=True
            ),
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID of the message',
                required=True
            )
        ],
        responses={
            200: MessageSerializer,
            401: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        tags=['Chat - Messages']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Delete a message",
        description="Delete a message from the conversation. Only the sender of the message can delete it.",
        parameters=[
            OpenApiParameter(
                name='conversation_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID of the conversation',
                required=True
            ),
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID of the message',
                required=True
            )
        ],
        responses={
            204: OpenApiTypes.NONE,
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        tags=['Chat - Messages']
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if instance.sender != self.request.user:
            raise PermissionDenied('You are not the sender of this message')
        instance.delete()