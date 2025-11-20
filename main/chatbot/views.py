import uuid
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import (extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse)
from drf_spectacular.types import OpenApiTypes
from .models import ChatMessage
from .serializers import (ChatRequestSerializer,ChatResponseSerializer,ChatHistorySerializer,HistoryResponseSerializer,)
from .ai_config import call_gemini, is_off_topic, OFF_TOPIC_RESPONSE

@extend_schema(
    methods=['POST'],
    tags=['Chatbot'],
    summary="Send a message to WanderBot (travel assistant)",
    description=(
        "Send a travel-related message to WanderBot, the AI assistant "
        "embedded in TravelEase. The bot maintains conversation history "
        "per session_id and only answers travel-related queries."
    ),
    request=ChatRequestSerializer,
    responses={
        200: OpenApiResponse(
            response=ChatResponseSerializer,
            description="Bot reply returned successfully",
            examples=[
                OpenApiExample(
                    name="Success",
                    value={
                        "success": True,
                        "message": "Best places to visit in Japan in April?",
                        "response": "April is cherry blossom season — Kyoto and Tokyo are stunning! ...",
                        "session_id": "abc-123-def-456",
                        "created_at": "2025-11-05T10:30:00Z",
                    },
                )
            ],
        ),
        400: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Validation error",
            examples=[
                OpenApiExample(
                    name="Validation Error",
                    value={
                        "success": False,
                        "error": "Validation failed",
                        "details": {"message": ["This field is required."]},
                    },
                )
            ],
        ),
        502: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Gemini API error",
            examples=[
                OpenApiExample(
                    name="Gemini Error",
                    value={
                        "success": False,
                        "error": "Gemini API error",
                        "details": "Gemini API returned 429",
                    },
                )
            ],
        ),
        503: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Network / service unreachable",
        ),
        504: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Request timed out",
        ),
        500: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Internal server error",
        ),
    },
    examples=[
        OpenApiExample(
            name="Basic Travel Question",
            value={"message": "What are the best beaches in Thailand?"},
            request_only=True,
        ),
        OpenApiExample(
            name="Question with Session (Conversation Memory)",
            value={
                "message": "How much should I budget per day there?",
                "session_id": "user-session-123",
            },
            request_only=True,
        ),
        OpenApiExample(
            name="Off-Topic Question (Will Be Rejected by Bot)",
            value={"message": "Write me a Python script"},
            request_only=True,
        ),
    ],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def chatbot(request):
    serializer = ChatRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": "Validation failed", "details": serializer.errors},status=status.HTTP_400_BAD_REQUEST,)
    validated_data = serializer.validated_data
    user_message = validated_data["message"]
    session_id = validated_data.get("session_id") or str(uuid.uuid4())
    if is_off_topic(user_message):
        bot_message = OFF_TOPIC_RESPONSE
    else:
        result = call_gemini(session_id=session_id, user_message=user_message)

        if not result["success"]:
            error = result.get("error", "Unknown error")
            code = result.get("status_code", 0)
            if "timeout" in error:
                return Response({"success": False, "error": "Request timed out", "message": "The chatbot took too long to respond."},status=status.HTTP_504_GATEWAY_TIMEOUT,)
            elif code == 0:
                return Response({"success": False, "error": "Service unavailable", "message": error},status=status.HTTP_503_SERVICE_UNAVAILABLE,)
            else:
                return Response({"success": False, "error": "Gemini API error", "details": error},status=status.HTTP_502_BAD_GATEWAY,)
        bot_message = result["text"]
    try:
        chat_message = ChatMessage.objects.create(
            user=request.user if request.user.is_authenticated else None,
            session_id=session_id,
            user_message=user_message,
            bot_response=bot_message,
        )
    except Exception as exc:
        return Response({"success": False, "error": "Internal server error", "message": str(exc)},status=status.HTTP_500_INTERNAL_SERVER_ERROR,)
    response_data = {
        "success": True,
        "message": user_message,
        "response": bot_message,
        "session_id": session_id,
        "created_at": chat_message.created_at,
    }
    return Response(ChatResponseSerializer(response_data).data, status=status.HTTP_200_OK)

@extend_schema(
    methods=['GET'],
    tags=['Chatbot'],
    summary="Retrieve chat history for a session",
    description="Returns all messages exchanged in a given session, ordered oldest to newest.",
    parameters=[
        OpenApiParameter(
            name='session_id',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.PATH,
            description='The session ID to retrieve history for',
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=HistoryResponseSerializer,
            description="Chat history returned successfully",
            examples=[
                OpenApiExample(
                    name="History Response",
                    value={
                        "success": True,
                        "session_id": "abc-123-def-456",
                        "count": 2,
                        "messages": [
                            {
                                "id": 1,
                                "user_message": "Best beaches in Bali?",
                                "bot_response": "Bali has stunning beaches like Seminyak, Nusa Dua...",
                                "created_at": "2025-11-05T10:30:00Z",
                            },
                            {
                                "id": 2,
                                "user_message": "What about budget?",
                                "bot_response": "Bali is very budget-friendly...",
                                "created_at": "2025-11-05T10:31:00Z",
                            },
                        ],
                    },
                )
            ],
        ),
        500: OpenApiResponse(response=OpenApiTypes.OBJECT, description="Internal server error"),
    },
)
@api_view(['GET'])
@permission_classes([AllowAny])
def chat_history(request, session_id):
    try:
        messages = ChatMessage.objects.filter(session_id=session_id).order_by('created_at')
        serializer = ChatHistorySerializer(messages, many=True)
        return Response({"success": True,"session_id": session_id,"count": messages.count(),"messages": serializer.data,},
                        status=status.HTTP_200_OK,)
    except Exception as exc:
        return Response({"success": False, "error": "Failed to retrieve history", "message": str(exc)},status=status.HTTP_500_INTERNAL_SERVER_ERROR,)