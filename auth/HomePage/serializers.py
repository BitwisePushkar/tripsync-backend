from rest_framework import serializers

class WeatherSerializer(serializers.Serializer):
    location = serializers.CharField(max_length=100)
    temperature = serializers.FloatField(min_value=-100,max_value=100)
    wind = serializers.FloatField(min_value=0,max_value=500)
    chance_of_rain = serializers.IntegerField(min_value=0,max_value=100)
    
    def validate_temperature(self, value):
        if value < -100 or value > 100:
            raise serializers.ValidationError("Temperature must be between -100°C and 100°C")
        return value
    
    def validate_wind(self, value):
        if value < 0:
            raise serializers.ValidationError("Wind speed cannot be negative")
        return value
    
    def validate_chance_of_rain(self, value):
        if not 0 <= value <= 100:
            raise serializers.ValidationError("Chance of rain must be between 0 and 100")
        return value