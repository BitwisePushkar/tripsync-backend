from django.db import models
from django.conf import settings 
from django.db.models import Prefetch
from django.apps import apps 

class ConversationManager(models.Manager):
    def get_queryset(self):
        UserModel = apps.get_model(settings.AUTH_USER_MODEL)  
        return super().get_queryset().prefetch_related(
            Prefetch('participants', queryset=UserModel.objects.only('id', 'username'))
        )

class Conversation(models.Model):
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ConversationManager()

    def __str__(self):
        participant_names = ", ".join([user.username for user in self.participants.all()])
        return f"Conversation with {participant_names}"

class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.sender.username}: {self.content[:20]}"
