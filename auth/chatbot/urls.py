from django.urls import path
from .views import chatbot, chat_history

urlpatterns = [
    path('', chatbot, name='chatbot'),
    path('history/<str:session_id>/', chat_history, name='chat-history'),
]