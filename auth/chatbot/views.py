import requests
import uuid
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from .models import ChatMessage
from .serializers import (ChatRequestSerializer, ChatResponseSerializer,
    ChatHistorySerializer,
    HistoryResponseSerializer)


@extend_schema(
    request=ChatRequestSerializer,
    responses={200: ChatResponseSerializer},
    examples=[
        OpenApiExample(
            'Basic Chat',
            value={
                'message': 'Best Place to go?',
            },
            request_only=True,
        ),
        OpenApiExample(
            'Chat with Custom Prompt',
            value={
                'message': 'Tell how to travek safely',
                'system_prompt': 'You are a professional traveller explain how to travel safely in points',
            },
            request_only=True,
        ),
        OpenApiExample(
            'Chat with Session',
            value={
                'message': 'Continue our previous discussion',
                'system_prompt': 'You are a helpful assistant',
                'session_id': 'user-session-123'
            },
            request_only=True,
        ),
        OpenApiExample(
            'Success Response',
            value={
                'success': True,
                'message': 'what should I do for a adventorous trip?',
                'response': 'To make your trip adventorous make sure to go to...',
                'session_id': 'abc-123-def-456',
                'created_at': '2025-11-05T10:30:00Z'
            },
            response_only=True,
        ),
    ],
    description='Send a message to the AI assistant'
)
@api_view(['POST'])
@permission_classes([AllowAny])
def chatbot(request):
    serializer = ChatRequestSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'error': 'Validation failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    validated_data = serializer.validated_data
    user_message = validated_data['message']
    system_prompt = validated_data.get('system_prompt', 'You are a helpful AI assistant for planning trip your whole goal is to answer trip related questions and make sure to only answer trip/travelling related questions. Keep the answers concise and short ')
    session_id = validated_data.get('session_id', str(uuid.uuid4()))
    
    try:
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={settings.GOOGLE_API_KEY}"
        
        payload = {
            "contents": [{
                "parts": [{"text": f"{system_prompt}\n\nUser: {user_message}"}]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 2048,
            }
        }
        
        response = requests.post(
            gemini_url, 
            headers={'Content-Type': 'application/json'}, 
            json=payload, 
            timeout=30
        )
        
        if response.status_code != 200:
            return Response({
                'success': False,
                'error': 'Gemini API error',
                'details': response.text
            }, status=status.HTTP_502_BAD_GATEWAY)
        
        gemini_response = response.json()
        bot_message = gemini_response.get('candidates', [{}])[0]\
            .get('content', {})\
            .get('parts', [{}])[0]\
            .get('text', 'No response generated')
        
        chat_message = ChatMessage.objects.create(
            user=request.user if request.user.is_authenticated else None,
            session_id=session_id,
            user_message=user_message,
            bot_response=bot_message,
            system_prompt=system_prompt
        )
        
        response_data = {
            'success': True,
            'message': user_message,
            'response': bot_message,
            'session_id': session_id,
            'created_at': chat_message.created_at
        }
        
        response_serializer = ChatResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
        
    except requests.exceptions.Timeout:
        return Response({
            'success': False,
            'error': 'Request timed out',
            'message': 'The chatbot took too long to respond'
        }, status=status.HTTP_504_GATEWAY_TIMEOUT)
        
    except requests.exceptions.RequestException as e:
        return Response({
            'success': False,
            'error': 'Request failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': 'Internal server error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    parameters=[
        OpenApiParameter(
            name='session_id',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.PATH,
            description='Session ID to retrieve chat history'
        ),
    ],
    responses={200: HistoryResponseSerializer},
    examples=[
        OpenApiExample(
            'History Response',
            value={
                'success': True,
                'session_id': 'abc-123-def-456',
                'count': 2,
                'messages': [
                    {
                        'id': 1,
                        'user_message': 'Hello',
                        'bot_response': 'Hi! How can I help you?',
                        'created_at': '2025-11-05T10:30:00Z'
                    },
                    {
                        'id': 2,
                        'user_message': 'What is AI?',
                        'bot_response': 'AI stands for Artificial Intelligence...',
                        'created_at': '2025-11-05T10:31:00Z'
                    }
                ]
            },
            response_only=True,
        ),
    ],
    description='Retrieve chat history for a specific session'
)
@api_view(['GET'])
@permission_classes([AllowAny])
def chat_history(request, session_id):
    try:
        messages = ChatMessage.objects.filter(session_id=session_id).order_by('created_at')
        serializer = ChatHistorySerializer(messages, many=True)
        
        return Response({
            'success': True,
            'session_id': session_id,
            'count': messages.count(),
            'messages': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': 'Failed to retrieve history',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
