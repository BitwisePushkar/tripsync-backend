from django.db import models

class WeatherCache(models.Model):
    location = models.CharField(max_length=100, unique=True)
    temperature = models.FloatField()
    wind = models.FloatField()
    chance_of_rain = models.IntegerField()

    def __str__(self):
        return self.location