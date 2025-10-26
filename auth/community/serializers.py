from rest_framework import serializers
from .models import Post

class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ['title','desc','loc','loc_rating','img','vid','created-at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']   

    class Meta:
        ordering = ['-created_at']

    def get_img_url(self, obj):
        if obj.img:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.img.url)
            return obj.img.url
        return None
    
    def get_vid_url(self, obj):
        if obj.vid:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.vid.url)
            return obj.vid.url
        return None

    def validate_img(self, value):
        if value:
            if value.size > 10 * 1024 * 1024:
                raise serializers.ValidationError("Image size should not exceed 10MB")
            validext = ['jpg', 'jpeg', 'png', 'webp']
            ext = value.name.split('.')[-1].lower()
            if ext not in validext:
                raise serializers.ValidationError(f"Invalid image format.")
        return value
    
    def validate_vid(self, value):
        if value:
            if value.size > 100 * 1024 * 1024:
                raise serializers.ValidationError("Video size should not exceed 100MB")
            validext = ['mp4', 'mov', 'avi', 'mkv', 'webm']
            ext = value.name.split('.')[-1].lower()
            if ext not in validext:
                raise serializers.ValidationError(f"Invalid video format.")
        return value
    
    def __str__(self):
        return self.title

        