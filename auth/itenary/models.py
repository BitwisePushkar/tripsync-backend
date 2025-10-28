from django.db import models
from django.contrib.auth.models import User

class Itenary(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    destination = models.CharField(max_length=200)
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    days = models.IntegerField()
    Genre = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.destination} - {self.days} days"


    