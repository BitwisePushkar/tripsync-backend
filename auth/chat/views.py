from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample,OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from django.db.models import Count, Q
from account.models import User
from .models import Conversation, Message
from .serializers import (ConversationSerializer, MessageSerializer, CreateMessageSerializer,CreateConversationSerializer,ConversationDetailSerializer)
from django.utils import timezone

class ConversationListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateConversationSerializer
        return ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(participants=self.request.user).prefetch_related('participants', 'messages').annotate(message_count=Count('messages')).order_by('-updated_at')
    
    @extend_schema(
        summary="List user's conversations",
        description="Retrieve all conversations where the authenticated user is a participant.",
        tags=['Chat - Conversations'],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Conversations retrieved successfully",
                examples=[
                    OpenApiExample(
                        name="Success Response",
                        value={
                            "status": "success",
                            "message": "Conversations retrieved successfully",
                            "data": [
                                {
                                    "id": 1,
                                    "name": "Trip Planning Group",
                                    "participants": [
                                        {"id": 1, "email": "you@example.com"},
                                        {"id": 2, "email": "friend@example.com"}
                                    ],
                                    "last_message": {
                                        "id": 101,
                                        "content": "Let's finalize the itinerary!",
                                        "sender": {"id": 2},
                                        "timestamp": "2025-11-04T18:30:00Z"
                                    },
                                    "message_count": 12,
                                    "updated_at": "2025-11-04T19:00:00Z"
                                }
                            ]
                        }
                    )
                ]
            ),
            401: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Unauthorized access",
                examples=[
                    OpenApiExample(
                        name="Unauthorized Response",
                        value={
                            "status": "error",
                            "message": "Authentication credentials were not provided.",
                            "errors": {"detail": ["You must be logged in to view conversations."]}
                        }
                    )
                ]
            )
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        summary="Create a conversation",
        description="Create a new conversation (DM or group). If a DM already exists between two users, the existing conversation is returned.",
        request=CreateConversationSerializer,
        tags=['Chat - Conversations'],
        examples=[
            OpenApiExample(
                "Direct Message Example",
                value={"participant_ids": [2]},
                request_only=True,
            ),
            OpenApiExample(
                "Group Chat Example",
                value={"participant_ids": [2, 3, 4], "name": "Trip Planning Group"},
                request_only=True,
            ),
        ],
        responses={
            201: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Conversation created successfully",
                examples=[
                    OpenApiExample(
                        name="Success Response",
                        value={
                            "status": "success",
                            "message": "Conversation created successfully",
                            "data": {
                                "id": 5,
                                "name": "Trip Planning Group",
                                "participants": [
                                    {"id": 1, "email": "you@example.com"},
                                    {"id": 2, "email": "friend@example.com"},
                                    {"id": 3, "email": "member@example.com"}
                                ],
                                "message_count": 0,
                                "updated_at": "2025-11-04T20:10:00Z"
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Invalid data provided",
                examples=[
                    OpenApiExample(
                        name="Validation Error",
                        value={
                            "status": "error",
                            "message": "Invalid request data",
                            "errors": {"participant_ids": ["At least one participant is required."]}
                        }
                    )
                ]
            ),
            401: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Unauthorized access",
                examples=[
                    OpenApiExample(
                        name="Unauthorized Response",
                        value={
                            "status": "error",
                            "message": "Authentication credentials were not provided.",
                            "errors": {"detail": ["You must be logged in to create a conversation."]}
                        }
                    )
                ]
            ),
        },
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
        description="Retrieve details of a specific conversation.",
        tags=["Chat - Conversations"],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Conversation details retrieved successfully",
                examples=[
                    OpenApiExample(
                        name="Success Response",
                        value={
                            "status": "success",
                            "message": "Conversation details retrieved successfully",
                            "data": {
                                "id": 3,
                                "name": "Trip to Kerala",
                                "participants": [
                                    {"id": 1, "email": "you@example.com"},
                                    {"id": 2, "email": "friend@example.com"}
                                ],
                                "messages": [
                                    {"id": 21, "content": "Booked tickets!", "sender": {"id": 1}},
                                    {"id": 22, "content": "Awesome!", "sender": {"id": 2}}
                                ],
                                "updated_at": "2025-11-04T20:00:00Z"
                            }
                        }
                    )
                ],
            ),
            403: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="User not a participant of this conversation",
                examples=[
                    OpenApiExample(
                        name="Forbidden Response",
                        value={
                            "status": "error",
                            "message": "Access denied",
                            "errors": {"detail": ["You are not a participant of this conversation."]}
                        }
                    )
                ],
            ),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Conversation not found",
                examples=[
                    OpenApiExample(
                        name="Not Found Response",
                        value={
                            "status": "error",
                            "message": "Conversation not found",
                            "errors": {"detail": ["Conversation does not exist"]}
                        }
                    )
                ],
            ),
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Leave conversation",
        description="Leave a conversation.",
        tags=["Chat - Conversations"],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="User left the conversation successfully",
                examples=[
                    OpenApiExample(
                        name="Success Response",
                        value={
                            "status": "success",
                            "message": "You have left the conversation successfully"
                        }
                    )
                ],
            ),
            403: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="User not a participant",
                examples=[
                    OpenApiExample(
                        name="Forbidden Response",
                        value={
                            "status": "error",
                            "message": "Access denied",
                            "errors": {"detail": ["You are not a participant of this conversation."]}
                        }
                    )
                ],
            ),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Conversation not found",
                examples=[
                    OpenApiExample(
                        name="Not Found Response",
                        value={
                            "status": "error",
                            "message": "Conversation not found",
                            "errors": {"detail": ["Conversation does not exist"]}
                        }
                    )
                ],
            ),
        },
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
        return Message.objects.filter(conversation=conversation).select_related('sender').order_by('timestamp')
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateMessageSerializer
        return MessageSerializer

    @extend_schema(
    summary="List messages",
    description="Retrieve all messages from a conversation. Only participants can access messages.",
    tags=["Chat - Conversations"],
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Messages retrieved successfully",
            examples=[
                OpenApiExample(
                    name="Success Response",
                    value={
                        "status": "success",
                        "message": "Messages retrieved successfully.",
                        "data": [
                            {
                                "id": 1,
                                "sender": {"id": 2, "email": "friend@example.com"},
                                "content": "Hey, ready for the trip?",
                                "timestamp": "2025-11-05T09:45:00Z"
                            },
                            {
                                "id": 2,
                                "sender": {"id": 1, "email": "you@example.com"},
                                "content": "Yes, let's go!",
                                "timestamp": "2025-11-05T09:46:00Z"
                            }
                        ]
                    }
                )
            ]
        ),
        403: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="User not a participant of this conversation",
            examples=[
                OpenApiExample(
                    name="Forbidden",
                    value={
                        "status": "error",
                        "message": "You are not a participant of this conversation.",
                        "errors": {"conversation": ["Access denied."]}
                    }
                )
            ]
        ),
        404: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Conversation not found",
            examples=[
                OpenApiExample(
                    name="Not Found",
                    value={
                        "status": "error",
                        "message": "Conversation not found.",
                        "errors": {"conversation_id": ["Invalid conversation ID."]}
                    }
                )
            ]
        ),
    },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
    summary="Send message",
    description="Send a message in a conversation where the authenticated user is a participant.",
    tags=["Chat - Conversations"],
    request=CreateMessageSerializer,
    responses={
        201: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Message sent successfully",
            examples=[
                OpenApiExample(
                    name="Success Response",
                    value={
                        "status": "success",
                        "message": "Message sent successfully.",
                        "data": {
                            "id": 45,
                            "sender": {"id": 1, "email": "you@example.com"},
                            "content": "What time are we leaving?",
                            "timestamp": "2025-11-05T11:00:00Z"
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Invalid input data",
            examples=[
                OpenApiExample(
                    name="Validation Error",
                    value={
                        "status": "error",
                        "message": "Invalid input data.",
                        "errors": {"content": ["This field may not be blank."]}
                    }
                )
            ]
        ),
        403: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="User not a participant of this conversation",
            examples=[
                OpenApiExample(
                    name="Forbidden",
                    value={
                        "status": "error",
                        "message": "You are not a participant of this conversation.",
                        "errors": {"conversation": ["Access denied."]}
                    }
                )
            ]
        ),
    },
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
    description="Retrieve details of a specific message from a conversation.",
    tags=["Chat - Conversations"],
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Message retrieved successfully",
            examples=[
                OpenApiExample(
                    name="Success Response",
                    value={
                        "status": "success",
                        "message": "Message retrieved successfully.",
                        "data": {
                            "id": 23,
                            "sender": {"id": 2, "email": "friend@example.com"},
                            "content": "Don't forget snacks!",
                            "timestamp": "2025-11-05T08:00:00Z"
                        }
                    }
                )
            ]
        ),
        403: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="User not a participant of this conversation",
            examples=[
                OpenApiExample(
                    name="Forbidden",
                    value={
                        "status": "error",
                        "message": "You are not a participant of this conversation.",
                        "errors": {"conversation": ["Access denied."]}
                    }
                )
            ]
        ),
        404: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Message not found",
            examples=[
                OpenApiExample(
                    name="Not Found",
                    value={
                        "status": "error",
                        "message": "Message not found.",
                        "errors": {"message_id": ["Invalid message ID."]}
                    }
                )
            ]
        ),
    },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
    summary="Edit message",
    description="Edit your own message content.",
    tags=["Chat - Conversations"],
    request=OpenApiTypes.OBJECT,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Message updated successfully",
            examples=[
                OpenApiExample(
                    name="Success Response",
                    value={
                        "status": "success",
                        "message": "Message updated successfully.",
                        "data": {
                            "id": 23,
                            "content": "Updated message content",
                            "edited_at": "2025-11-05T10:30:00Z"
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Invalid input data",
            examples=[
                OpenApiExample(
                    name="Validation Error",
                    value={
                        "status": "error",
                        "message": "Invalid data provided.",
                        "errors": {"content": ["This field may not be blank."]}
                    }
                )
            ]
        ),
        403: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="User not allowed to edit message",
            examples=[
                OpenApiExample(
                    name="Forbidden",
                    value={
                        "status": "error",
                        "message": "You can only edit your own messages.",
                        "errors": {"permission": ["Access denied."]}
                    }
                )
            ]
        ),
        404: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Message not found",
            examples=[
                OpenApiExample(
                    name="Not Found",
                    value={
                        "status": "error",
                        "message": "Message not found.",
                        "errors": {"message_id": ["Invalid message ID."]}
                    }
                )
            ]
        ),
    },
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
    summary="Delete message",
    description="Delete your own message.",
    tags=["Chat - Conversations"],
    responses={
        204: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Message deleted successfully",
            examples=[
                OpenApiExample(
                    name="Success Response",
                    value={
                        "status": "success",
                        "message": "Message deleted successfully."
                    }
                )
            ]
        ),
        403: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="User not allowed to delete message",
            examples=[
                OpenApiExample(
                    name="Forbidden",
                    value={
                        "status": "error",
                        "message": "You can only delete your own messages.",
                        "errors": {"permission": ["Access denied."]}
                    }
                )
            ]
        ),
        404: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Message not found",
            examples=[
                OpenApiExample(
                    name="Not Found",
                    value={
                        "status": "error",
                        "message": "Message not found.",
                        "errors": {"message_id": ["Invalid message ID."]}
                    }
                )
            ]
        ),
    },
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)
    def perform_update(self, serializer):
        if serializer.instance.sender != self.request.user:
            raise PermissionDenied('You can only edit your own messages')
        serializer.save(edited_at=timezone.now())
    def perform_destroy(self, instance):
        if instance.sender != self.request.user:
            raise PermissionDenied('You can only delete your own messages')
        instance.delete()