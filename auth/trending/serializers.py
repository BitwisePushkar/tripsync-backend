from rest_framework import serializers
from .models import TrendingPlace, FunFact

class FunFactSerializer(serializers.ModelSerializer):
    class Meta:
        model = FunFact
        fields = ['id', 'slide', 'title', 'desc', 'photo']

class TrendingPlaceSerializer(serializers.ModelSerializer):
    fun_facts = FunFactSerializer(many=True, read_only=True)
    class Meta:
        model = TrendingPlace
        fields = ['id', 'name', 'main', 'fun_facts']

class TrendingPlaceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrendingPlace
        fields = ['id', 'name', 'main']

class FunFactCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FunFact
        fields = ['id', 'place', 'slide', 'title', 'desc', 'photo']
    
    def validate_desc(self, value):
        word_count = len(value.split())
        if word_count > 250:raise serializers.ValidationError(" Maximum 250 words allowed.")
        return value
    
    def validate(self, data):
        place = data.get('place')
        if self.instance:
            existing_count = FunFact.objects.filter(place=place).exclude(id=self.instance.id).count()
        else:
            existing_count = FunFact.objects.filter(place=place).count()
        if existing_count >= 10:
            raise serializers.ValidationError("Cannot add more fun facts. Maximum 10 slides allowed per place.")
        return data