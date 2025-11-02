from rest_framework import serializers
from .models import Trip
from datetime import datetime

class TripSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ['id', 'tripname', 'current_loc', 'destination', 'trending','start_date', 'end_date', 'days', 'trip_type', 'trip_preferences','budget', 'itinerary_data', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'trending', 'budget']    
    def validate(self, data):
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError({"end_date": "End date must be after start date"})
            days_diff = (data['end_date'] - data['start_date']).days + 1
            data['days'] = days_diff
        return data

class TripCreateSerializer(serializers.ModelSerializer):
    use_ai = serializers.BooleanField(default=True, write_only=True)    
    class Meta:
        model = Trip
        fields = ['tripname', 'current_loc', 'destination','start_date', 'end_date', 'trip_type', 'trip_preferences', 'use_ai']
    
    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError({"end_date": "End date must be after start date"})       
        if data['start_date'] < datetime.now().date():
            raise serializers.ValidationError({"start_date": "Start date cannot be in the past"})        
        days_diff = (data['end_date'] - data['start_date']).days + 1
        data['days'] = days_diff        
        if days_diff > 7:
            raise serializers.ValidationError({"end_date": "Trip duration cannot exceed 7 days"})
        data.pop('use_ai', None)       
        return data

class TripManualCreateSerializer(serializers.ModelSerializer):
    use_ai = serializers.BooleanField(default=False, write_only=True)
    itinerary_data = serializers.JSONField(required=True)    
    class Meta:
        model = Trip
        fields = ['tripname', 'current_loc', 'destination','start_date', 'end_date', 'trip_type', 'trip_preferences','use_ai', 'itinerary_data']    
    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError({"end_date": "End date must be after start date"})        
        if data['start_date'] < datetime.now().date():
            raise serializers.ValidationError({"start_date": "Start date cannot be in the past"})        
        days_diff = (data['end_date'] - data['start_date']).days + 1
        data['days'] = days_diff        
        if days_diff > 7:
            raise serializers.ValidationError({"end_date": "Trip duration cannot exceed 7 days"})
        itinerary = data.get('itinerary_data')
        if not isinstance(itinerary, dict):
            raise serializers.ValidationError({"itinerary_data": "Itinerary data must be a dictionary"})        
        if 'days' not in itinerary:
            raise serializers.ValidationError({"itinerary_data": "Itinerary data must contain 'days' key"})        
        if not isinstance(itinerary['days'], list):
            raise serializers.ValidationError({"itinerary_data": "'days' must be a list"})        
        if len(itinerary['days']) != days_diff:
            raise serializers.ValidationError({"itinerary_data": f"Number of days in itinerary ({len(itinerary['days'])}) must match trip duration ({days_diff} days)"})
        for idx, day in enumerate(itinerary['days']):
            if not isinstance(day, dict):
                raise serializers.ValidationError({"itinerary_data": f"Day {idx + 1} must be a dictionary"})            
            required_fields = ['day_number', 'title', 'activities']
            for field in required_fields:
                if field not in day:
                    raise serializers.ValidationError({"itinerary_data": f"Day {idx + 1} must contain '{field}' field"})           
            if day['day_number'] != idx + 1:
                raise serializers.ValidationError({"itinerary_data": f"Day number must be {idx + 1}, got {day['day_number']}"})
            if not isinstance(day['activities'], list):
                raise serializers.ValidationError({"itinerary_data": f"Day {idx + 1} activities must be a list"})            
            if len(day['activities']) == 0:
                raise serializers.ValidationError({"itinerary_data": f"Day {idx + 1} must have at least one activity"})
            valid_time_slots = ['morning', 'afternoon', 'evening', 'night']
            for act_idx, activity in enumerate(day['activities']):
                if not isinstance(activity, dict):
                    raise serializers.ValidationError({"itinerary_data": f"Day {idx + 1}, Activity {act_idx + 1} must be a dictionary"})                
                required_activity_fields = ['time_slot', 'title', 'description', 'location', 'duration', 'estimated_cost']
                for field in required_activity_fields:
                    if field not in activity:
                        raise serializers.ValidationError({"itinerary_data": f"Day {idx + 1}, Activity {act_idx + 1} must contain '{field}' field"})
                if activity['time_slot'] not in valid_time_slots:
                    raise serializers.ValidationError({"itinerary_data": f"Day {idx + 1}, Activity {act_idx + 1}: Invalid time_slot. Must be one of {valid_time_slots}"})
                try:
                    float(activity['estimated_cost'])
                except (ValueError, TypeError):
                    raise serializers.ValidationError({"itinerary_data": f"Day {idx + 1}, Activity {act_idx + 1}: estimated_cost must be a number"})
        data.pop('use_ai', None)       
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