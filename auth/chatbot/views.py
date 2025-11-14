import requests
import uuid
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from .models import ChatMessage
from .serializers import (ChatRequestSerializer, ChatResponseSerializer,ChatHistorySerializer,HistoryResponseSerializer)

@extend_schema(
    methods=['POST'],
    tags=['Chatbot'],
    summary="Send a message to the AI chatbot",
    description="Send a message to the AI chatbot powered by Google Gemini 2.0.",
    request=ChatRequestSerializer,
    responses={
        200: OpenApiResponse(
            response=ChatResponseSerializer,
            description="Chatbot response returned successfully",
            examples=[
                OpenApiExample(
                    name="Success Response",
                    value={
                        'success': True,
                        'message': 'what should I do for a adventorous trip?',
                        'response': 'To make your trip adventorous make sure to go to...',
                        'session_id': 'abc-123-def-456',
                        'created_at': '2025-11-05T10:30:00Z'
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Validation failed",
            examples=[
                OpenApiExample(
                    name="Validation Error",
                    value={
                        'success': False,
                        'error': 'Validation failed',
                        'details': {'message': ['This field is required.']}
                    }
                )
            ]
        ),
        502: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Gemini API error",
            examples=[
                OpenApiExample(
                    name="Gemini API Error",
                    value={
                        'success': False,
                        'error': 'Gemini API error',
                        'details': 'Detailed API error response here'
                    }
                )
            ]
        ),
        503: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Service unavailable or network issue",
            examples=[
                OpenApiExample(
                    name="Service Unavailable",
                    value={
                        'success': False,
                        'error': 'Service unavailable',
                        'message': 'Gemini service is temporarily unreachable.'
                    }
                )
            ]
        ),
        504: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Request timed out",
            examples=[
                OpenApiExample(
                    name="Timeout Error",
                    value={
                        'success': False,
                        'error': 'Request timed out',
                        'message': 'The chatbot took too long to respond'
                    }
                )
            ]
        ),
        500: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Internal server error",
            examples=[
                OpenApiExample(
                    name="Internal Error",
                    value={
                        'success': False,
                        'error': 'Internal server error',
                        'message': 'Detailed error message'
                    }
                )
            ]
        )
    },
    examples=[
        OpenApiExample(
            name="Basic Chat",
            value={'message': 'Best Place to go?'},
            request_only=True
        ),
        OpenApiExample(
            name="Chat with Custom Prompt",
            value={
                'message': 'Tell how to travek safely',
                'system_prompt': 'You are a professional traveller explain how to travel safely in points.'
            },
            request_only=True
        ),
        OpenApiExample(
            name="Chat with Session",
            value={
                'message': 'Continue our previous discussion',
                'system_prompt': 'You are a helpful assistant',
                'session_id': 'user-session-123'
            },
            request_only=True
        )
    ]
)

@api_view(['POST'])
@permission_classes([AllowAny])
def chatbot(request):
    serializer = ChatRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'success': False,'error': 'Validation failed','details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
    validated_data = serializer.validated_data
    user_message = validated_data['message']
    system_prompt = validated_data.get('system_prompt', 
        '''You are a specialized trip planning assistant. Your sole purpose is to help users with travel and trip planning.

CRITICAL INSTRUCTION - READ CAREFULLY:
You must REFUSE to answer ANY question that is not directly related to travel and trip planning. This is NON-NEGOTIABLE.

ALLOWED TOPICS ONLY:
- Trip destinations and recommendations
- Travel itineraries and schedules
- Hotels, accommodations, bookings
- Flights, trains, buses, transportation
- Tourist attractions and activities
- Travel tips, safety, packing
- Visa, passport, travel documents
- Local customs and culture for travelers
- Travel budgets and expenses
- Weather and best travel times

STRICT RESPONSE PROTOCOL:
If the user asks about ANYTHING else (science, technology, entertainment, general knowledge, recipes, etc.), you MUST respond with EXACTLY this message and NOTHING else:
"I'm a trip planning assistant. Let's keep our conversation focused on your travel plans. How can I help with your trip?"

DO NOT:
- Provide any information outside of travel topics
- Try to relate non-travel topics to travel
- Answer "just this once" 
- Use bold text, asterisks, or markdown formatting
- Write more than 3-4 sentences

Your responses must be brief, practical, and ONLY about travel.''')
    session_id = validated_data.get('session_id', str(uuid.uuid4()))
    
    try:
<<<<<<< HEAD
        previous_messages = ChatMessage.objects.filter(
            session_id=session_id
        ).order_by('-created_at')[:5][::-1]
        
        conversation_history = []
        for msg in previous_messages:
            conversation_history.append({
                "role": "user",
                "parts": [{"text": msg.user_message}]
            })
            conversation_history.append({
                "role": "model",
                "parts": [{"text": msg.bot_response}]
            })
        
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={settings.GOOGLE_API_KEY}"
        
        conversation_history.append({
            "role": "user",
            "parts": [{"text": user_message}]
        })
        
=======
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={settings.GOOGLE_API_KEY}"
               
>>>>>>> f03ca41fa1dd46e2421eb99c0074ec8c6e38a5f3
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"[SYSTEM INSTRUCTION — MUST FOLLOW STRICTLY THESE ARE NON NEGOTIABLE IN ANY SCENARIO]\n{system_prompt}"}]
                },
            ] + conversation_history,

            "generationConfig": {
                "temperature": 0.3,
                "topK": 20,
                "topP": 0.8,
                "maxOutputTokens": 1000,
                "stopSequences": ["\n\n"]
            }
        }
        
        response = requests.post(gemini_url, headers={'Content-Type': 'application/json'}, json=payload, timeout=30)
        
        if response.status_code != 200:
            return Response({'success': False,'error': 'Gemini API error','details': response.text}, status=status.HTTP_502_BAD_GATEWAY)
        
        gemini_response = response.json()
        bot_message = gemini_response.get('candidates', [{}])[0]\
            .get('content', {})\
            .get('parts', [{}])[0]\
            .get('text', 'No response generated')
        
        bot_message = bot_message.replace('**', '').replace('*', '').replace('__', '').replace('##', '').replace('#', '').strip()
        
        if len(bot_message) > 400:
            sentences = bot_message.split('. ')
            bot_message = '. '.join(sentences[:3]) + '.'
        
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
        return Response({'success': False,'error': 'Request timed out','message': 'The chatbot took too long to respond'}, status=status.HTTP_504_GATEWAY_TIMEOUT)
    except requests.exceptions.RequestException as e:
        return Response({'success': False,'error': 'Request failed','message': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        return Response({'success': False,'error': 'Internal server error','message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    methods=['GET'],
    tags=['Chatbot'],
    summary="Retrieve chat history",
    description="Retrieve chat history for a specific session using the session ID.",
    parameters=[
        OpenApiParameter(
            name='session_id',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.PATH,
            description='Session ID to retrieve chat history'
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=HistoryResponseSerializer,
            description="Chat history retrieved successfully",
            examples=[
                OpenApiExample(
                    name="History Response",
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
                    }
                )
            ]
        ),
        500: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Failed to retrieve chat history",
            examples=[
                OpenApiExample(
                    name="Internal Error",
                    value={
                        'success': False,
                        'error': 'Failed to retrieve history',
                        'message': 'Detailed error message'
                    }
                )
            ]
        )
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def chat_history(request, session_id):
    try:
        messages = ChatMessage.objects.filter(session_id=session_id).order_by('created_at')
        serializer = ChatHistorySerializer(messages, many=True)
        
        return Response({'success': True,'session_id': session_id,'count': messages.count(),'messages': serializer.data}, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'success': False,'error': 'Failed to retrieve history','message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)