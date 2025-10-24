from django.db import models
from django.contrib.auth.models import User

class Itinerary(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    destination = models.CharField(max_length=200)
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    days = models.IntegerField()
    activity_genre = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.destination} - {self.days} days"

class ItineraryDay(models.Model):
    itinerary = models.ForeignKey(Itinerary, on_delete=models.CASCADE, related_name='day_plans')
    day_number = models.IntegerField()
    title = models.CharField(max_length=300)
    description = models.TextField()
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    genre = models.CharField(max_length=100)
    time = models.CharField(max_length=100)  
    location = models.CharField(max_length=200, blank=True)
    class Meta:
        ordering = ['day_number', 'id']
    
    def __str__(self):
        return f"Day {self.day_number}: {self.title}"