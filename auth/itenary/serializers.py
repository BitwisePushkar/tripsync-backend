from rest_framework import serializers
from .models import Itinerary, ItineraryDay

class ItineraryDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = ItineraryDay
        fields = ['id', 'day_number', 'title', 'description', 'cost', 'genre', 'time', 'location']

class ItinerarySerializer(serializers.ModelSerializer):
    day_plans = ItineraryDaySerializer(many=True, read_only=True)
    
    class Meta:
        model = Itinerary
        fields = ['id', 'destination', 'budget', 'days', 'activity_genre', 'created_at', 'day_plans']

class ItineraryRequestSerializer(serializers.Serializer):
    destination = serializers.CharField(max_length=200)
    budget = serializers.DecimalField(max_digits=10, decimal_places=2)
    days = serializers.IntegerField(min_value=1, max_value=30)
    activity_genre = serializers.CharField(max_length=100)