from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Case, When, Value, IntegerField
from django.conf import settings

class Trip(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='trips')
    tripname = models.CharField(max_length=100)
    current_loc = models.CharField(max_length=200)
    destination = models.CharField(max_length=200)
    trending = models.BooleanField(default=False)
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(30)])
    trip_type = models.CharField(max_length=50)
    trip_preferences = models.CharField(max_length=200)
    budget = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Trip'
        verbose_name_plural = 'Trips'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.tripname} - {self.destination}"

class Itinerary(models.Model):
    trip = models.OneToOneField(Trip, on_delete=models.CASCADE, related_name='itinerary')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Itinerary'
        verbose_name_plural = 'Itineraries'
    
    def __str__(self):
        return f"Itinerary for {self.trip.tripname}"

class DayPlan(models.Model):
    itinerary = models.ForeignKey(Itinerary, on_delete=models.CASCADE, related_name='day_plans')
    day_number = models.IntegerField()
    title = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['day_number']
        unique_together = ['itinerary', 'day_number']
    
    def __str__(self):
        return f"Day {self.day_number}: {self.title}"
    
class ActivityQuerySet(models.QuerySet):
    def ordered(self):
        return self.annotate(
            custom_order=Case(When(time='morning', then=Value(1)),
                              When(time='evening', then=Value(2)),
                              When(time='afternoon', then=Value(3)),
                              output_field=IntegerField(),)).order_by('custom_order', 'title')

class Activity(models.Model):
    day_plans = models.ForeignKey(DayPlan, on_delete=models.CASCADE, related_name='activities')   
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=500)
    location = models.CharField(max_length=200)
    time = models.CharField(max_length=10,choices=[('morning', 'Morning'), ('afternoon', 'Afternoon'), ('evening', 'Evening'),],blank=False,default='morning')
    timings = models.CharField()
    cost = models.FloatField(validators=[MinValueValidator(0)])
    category = models.CharField(max_length=400)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['day_plans', 'title']
    
    def __str__(self):
        return f"Activity {self.time}: {self.title}"