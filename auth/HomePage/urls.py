from django.urls import path
from .views import Weather

app_name = 'HomePage'

urlpatterns = [
    path('weather/', Weather.as_view(), name='current-weather'),
]