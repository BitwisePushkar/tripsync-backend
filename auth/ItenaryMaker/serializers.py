from rest_framework import serializers
from .models import Trip

class ItenarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ['id', 'tripname', 'current_loc', 'destination', 'trending', 'start_date', 'end_date', 'days', 'trip_type', 'trip_preferences', 'budget', 'Itenary_data','Itenary_json', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class ItenaryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ['tripname', 'current_loc', 'destination', 'start_date', 'end_date', 'days', 'trip_type', 'trip_preferences', 'budget']
    
    def validate(self, data):
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError("End date must be after start date")
        return data