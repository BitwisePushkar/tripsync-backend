from django.db import models
from account.models import User
from django.db.models import Prefetch

class ConversationManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().prefetch_related( Prefetch('participants', queryset=User.objects.only('id', 'email')))
    def for_user(self, user):
        return self.get_queryset().filter(participants=user)

class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name='conversations')
    name = models.CharField(max_length=255, null=True, blank=True) 
    is_group = models.BooleanField(default=False) 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True) 
    objects = ConversationManager()
    class Meta:
        ordering = ['-updated_at'] 
        indexes = [models.Index(fields=['-updated_at']),]

    def __str__(self):
        if self.name:
            return f'{self.name}'
        participant_emails = ", ".join([user.email for user in self.participants.all()[:3]])
        return f'Conversation with {participant_emails}'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.participants.count() > 2:
            self.is_group = True
            super().save(update_fields=['is_group'])
    
    @property
    def last_message(self):
        return self.messages.order_by('-timestamp').first()
    
    def is_participant(self, user):
        return self.participants.filter(id=user.id).exists()


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE,related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False) 
    edited_at = models.DateTimeField(null=True, blank=True) 

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['conversation', 'timestamp']),
            models.Index(fields=['conversation', '-timestamp']),
        ]

    def __str__(self):
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f'Message from {self.sender.email}: {preview}'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.conversation.save(update_fields=['updated_at'])