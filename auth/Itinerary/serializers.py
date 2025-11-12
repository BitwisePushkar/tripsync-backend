from rest_framework import serializers
from .models import Trip, Itinerary, DayPlan, Activity

class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = ['id','title','time','timings','cost','category','location','description','created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class DayPlanSerializer(serializers.ModelSerializer):
    activities = ActivitySerializer(many=True, read_only=True)
    
    class Meta:
        model = DayPlan
        fields = ['id', 'day_number','activities', 'title', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class ItinerarySerializer(serializers.ModelSerializer):
    day_plans = DayPlanSerializer(many=True, read_only=True)
    
    class Meta:
        model = Itinerary
        fields = ['id', 'day_plans', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class TripSerializer(serializers.ModelSerializer):
    itinerary = ItinerarySerializer(read_only=True)
    
    class Meta:
        model = Trip
        fields = ['id', 'tripname', 'current_loc', 'destination', 'trending','start_date', 'end_date', 'days', 'trip_type', 'trip_preferences','budget', 'itinerary', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class TripCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ['tripname', 'current_loc', 'destination', 'start_date', 'end_date', 'days', 'trip_type', 'trip_preferences']
    
    def validate(self, data):
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError("End Can't be Before Start Date")
        return data

class RegenerateItinerarySerializer(serializers.Serializer):
    tripname = serializers.CharField(max_length=100, required=False)
    current_loc = serializers.CharField(max_length=200, required=False)
    destination = serializers.CharField(max_length=200, required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    days = serializers.IntegerField(required=False)
    trip_type = serializers.CharField(max_length=50, required=False)
    trip_preferences = serializers.CharField(max_length=200, required=False)
    budget = serializers.FloatField(required=False)

class ActivityInputSerializer(serializers.Serializer):
    time = serializers.CharField(max_length=50)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField()
    location = serializers.CharField(max_length=300)
    cost = serializers.FloatField()
    category = serializers.CharField(max_length=50)
  
    def validate_category(self, value):
        valid_categories = ['sightseeing', 'dining', 'shopping', 'transportation', 'adventure', 'relaxation']
        if value.lower() not in valid_categories:
            raise serializers.ValidationError(f"Category must be one of: {', '.join(valid_categories)}")
        return value.lower()
    
    def validate_time(self, value):
        valid_times = ['Morning', 'Afternoon', 'Evening', 'Night']
        if value not in valid_times:
            raise serializers.ValidationError(f"Time must be one of: {', '.join(valid_times)}")
        return value

class ActivityUpdateSerializer(serializers.Serializer):
    time = serializers.CharField(max_length=50, required=False)
    title = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False)
    location = serializers.CharField(max_length=300, required=False)
    duration = serializers.CharField(max_length=50, required=False)
    cost = serializers.FloatField(required=False)
    category = serializers.CharField(max_length=50, required=False)
    
    def validate_category(self, value):
        valid_categories = ['sightseeing', 'dining', 'shopping', 'transportation', 'adventure', 'relaxation']
        if value.lower() not in valid_categories:
            raise serializers.ValidationError(f"Category must be one of: {', '.join(valid_categories)}")
        return value.lower()
    
    def validate_time(self, value):
        valid_times = ['Morning', 'Afternoon', 'Evening', 'Night']
        if value not in valid_times:
            raise serializers.ValidationError(f"Time must be one of: {', '.join(valid_times)}")
        return value
    
class ManualActivitySerializer(serializers.Serializer):
    time = serializers.CharField(max_length=50)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField()
    location = serializers.CharField(max_length=300)
    duration = serializers.CharField(max_length=50)
    cost = serializers.FloatField()
    category = serializers.CharField(max_length=50)
    
    def validate_category(self, value):
        valid_categories = ['sightseeing', 'dining', 'shopping', 'transportation', 'adventure', 'relaxation']
        if value.lower() not in valid_categories:
            raise serializers.ValidationError(f"Category must be one of: {', '.join(valid_categories)}")
        return value.lower()
    
    def validate_time(self, value):
        valid_times = ['Morning', 'Afternoon', 'Evening', 'Night']
        if value not in valid_times:
            raise serializers.ValidationError(f"Time must be one of: {', '.join(valid_times)}")
        return value

class ManualDayPlanSerializer(serializers.Serializer):
    day_number = serializers.IntegerField()
    title = serializers.CharField(max_length=200)
    activities = ManualActivitySerializer(many=True)
    
    def validate_day_number(self, value):
        if value < 1:
            raise serializers.ValidationError("Day number must be greater than 0")
        return value

class ManualItinerarySerializer(serializers.Serializer):
    day_plans = ManualDayPlanSerializer(many=True)
    
    def validate_day_plans(self, value):
        if not value:
            raise serializers.ValidationError("At least one day plan is required")
        
        day_numbers = [dp['day_number'] for dp in value]
        if len(day_numbers) != len(set(day_numbers)):
            raise serializers.ValidationError("Duplicate day numbers are not allowed")
        
        return value