from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib import settings

class ItenaryFields(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ItenaryFields')
    tripname = models.CharField(max_length=100)
    current_loc = models.CharField(max_legnth=200)
    destination = models.CharField(max_length=50)
    trending = models.CharField()
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.IntegerField(blank=True,null=True,validators=[MinValueValidator(1),MaxValueValidator(7)])
    trip_type = models.CharField()
    trip_preferences = models.CharField()
    Budget = models.FloatField()    

