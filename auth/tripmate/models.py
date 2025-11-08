from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from Itinerary.models import Trip

class Tripmate(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tripmate_profile')
    friends = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='user_tripmates', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Tripmate Profile'
        verbose_name_plural = 'Tripmate Profiles'
        indexes = [models.Index(fields=['user']),]
    
    def __str__(self):
        return f"{self.user.email}'s Tripmate Profile"
    
    def are_tripmates(self, other_user):
        return self.friends.filter(id=other_user.id).exists()
    
    def get_tripmate_count(self):
        return self.friends.count()


class FriendRequest(models.Model):  
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_friend_requests')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_friend_requests')
    status = models.CharField(max_length=10, choices=[('pending', 'Pending'),('accepted', 'Accepted'),('declined', 'Declined'),], default='pending')
    message = models.TextField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['sender', 'receiver']
        ordering = ['-created_at']
        indexes = [models.Index(fields=['receiver', 'status', '-created_at']),
                    models.Index(fields=['sender', 'status']),]
    
    def __str__(self):
        return f"{self.sender.email} -> {self.receiver.email} ({self.status})"
    
    def clean(self):
        if self.sender == self.receiver:
            raise ValidationError("Cannot send friend request to yourself")
        
        if Tripmate.objects.filter(user=self.sender, friends=self.receiver).exists():
            raise ValidationError("Already tripmates")


class TripMember(models.Model):  
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='trip_memberships')
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='added_members')
    permission = models.CharField(max_length=10, choices=[('view', 'View'),('edit', 'Edit'),], default='view')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['trip', 'user']
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user']),
                   models.Index(fields=['trip']),
                   models.Index(fields=['added_by']),]
    
    def __str__(self):
        return f"{self.trip.tripname} - {self.user.email} ({self.permission})"
    
    def clean(self):
        if self.user == self.trip.user:
            raise ValidationError("Cannot add trip owner as member")