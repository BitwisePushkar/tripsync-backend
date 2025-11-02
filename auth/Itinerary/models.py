from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings

class Trip(models.Model):    
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='trips')
    tripname = models.CharField(max_length=100)
    current_loc = models.CharField(max_length=200)
    destination = models.CharField(max_length=200)
    trending = models.BooleanField(default=False)
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.IntegerField(blank=True,null=True,validators=[MinValueValidator(1), MaxValueValidator(7)])
    trip_type = models.CharField(max_length=20,choices=[('group', 'Group Trip'),('solo', 'Solo Trip')])
    trip_preferences = models.CharField(max_length=20,choices=[('adventure', 'Adventure'),('relaxation', 'Relaxation'),('spiritual', 'Spiritual')])
    budget = models.FloatField(validators=[MinValueValidator(2000)])
    itinerary_data = models.JSONField(blank=True, null=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)   
    class Meta:
        ordering = ['-created_at']    
    def __str__(self):
        return f"{self.tripname} - {self.user.email}"