from rest_framework import serializers

class WeatherSerializer(serializers.Serializer):
    location = serializers.CharField()
    temperature = serializers.FloatField()
    wind = serializers.FloatField()
    chance_of_rain = serializers.IntegerField()