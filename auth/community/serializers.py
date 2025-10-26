from rest_framework import serializers
from .models import MediaFile

class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaFile
        fields = ['title','desc','loc','loc_rating','img','vid','created-at']

        