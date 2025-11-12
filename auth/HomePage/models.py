from django.db import models
from django.utils import timezone
from datetime import timedelta

class WeatherCache(models.Model):
    location = models.CharField(max_length=100, unique=True)
    temperature = models.FloatField()
    wind = models.FloatField()
    chance_of_rain = models.IntegerField()
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Weather Cache"
        verbose_name_plural = "Weather Caches"
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.location} - {self.temperature}°C (Updated: {self.updated_at.strftime('%Y-%m-%d %H:%M')})"
   
    def is_expired(self, minutes=30):
        return self.updated_at < timezone.now() - timedelta(minutes=minutes)