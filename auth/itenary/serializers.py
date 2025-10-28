from rest_framework import serializers
from .models import Itenary

class ItenarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Itenary
        fields = ['user','destination','budget','days','Genre','created_at']
        read_only_fields = ['user','created_at','Genre']