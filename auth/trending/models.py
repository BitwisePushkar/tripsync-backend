from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class TrendingPlace(models.Model):
    name = models.CharField(max_length=200)
    main = models.ImageField(upload_to='places/')
    def __str__(self):
        return self.name

class FunFact(models.Model):
    place = models.ForeignKey(TrendingPlace, on_delete=models.CASCADE, related_name='fun_facts')
    slide = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    title = models.CharField(max_length=100)
    desc = models.TextField(max_length=1500)
    photo = models.ImageField(upload_to='funfacts/')
    class Meta:
        ordering = ['slide']
        unique_together = ['place', 'slide']

    def __str__(self):
        return f"{self.place.name} - Slide {self.slide}"