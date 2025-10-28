from django.urls import path
from .views import Weather

urlpatterns = [
    path('weather/', Weather.as_view(), name='current-weather'),
]