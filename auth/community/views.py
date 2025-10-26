from rest_framework import serializers
from .models import Post

class PostSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    img_url = serializers.SerializerMethodField()
    vid_url = serializers.SerializerMethodField()

    