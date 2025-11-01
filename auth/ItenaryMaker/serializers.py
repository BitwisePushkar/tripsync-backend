from rest_framework import serializers
from .models import Trip
from datetime import datetime

class TripSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ['id', 'tripname', 'current_loc', 'destination', 'trending','start_date', 'end_date', 'days', 'trip_type', 'trip_preferences','budget', 'itinerary_data', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'trending', 'itinerary_data', 'budget']
    
    def validate(self, data):
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError({"end_date": "End date must be after start date"})
            days_diff = (data['end_date'] - data['start_date']).days + 1
            data['days'] = days_diff
        return data

class TripCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ['tripname', 'current_loc', 'destination','start_date', 'end_date', 'trip_type', 'trip_preferences']
    
    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError({"end_date": "End date must be after start date"})
        if data['start_date'] < datetime.now().date():
            raise serializers.ValidationError({"start_date": "Start date cannot be in the past"})
        days_diff = (data['end_date'] - data['start_date']).days + 1
        data['days'] = days_diff
        if days_diff > 7:
            raise serializers.ValidationError({"end_date": "Trip duration cannot exceed 7 days"})        
        return data

class TripListSerializer(serializers.ModelSerializer):
    has_itinerary = serializers.SerializerMethodField()   
    class Meta:
        model = Trip
        fields = ['id', 'tripname', 'destination', 'start_date', 'end_date','days', 'trip_type', 'budget', 'has_itinerary', 'created_at']  
    def get_has_itinerary(self, obj):
        return obj.itinerary_data is not None and bool(obj.itinerary_data)


class ItineraryUpdateSerializer(serializers.Serializer):
    itinerary_data = serializers.JSONField()    
    def validate_itinerary_data(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Itinerary data must be a dictionary")        
        if 'days' not in value:
            raise serializers.ValidationError("Itinerary data must contain 'days' key")       
        if not isinstance(value['days'], list):
            raise serializers.ValidationError("'days' must be a list")
        for day in value['days']:
            if not isinstance(day, dict):
                raise serializers.ValidationError("Each day must be a dictionary")            
            required_fields = ['day_number', 'title', 'activities']
            for field in required_fields:
                if field not in day:
                    raise serializers.ValidationError(f"Each day must contain '{field}' field")       
        return value