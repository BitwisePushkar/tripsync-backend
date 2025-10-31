from rest_framework import serializers
from .models import Post

class PostSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    img_url = serializers.SerializerMethodField()
    vid_url = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ['id', 'user_id','user_email','title', 'desc', 'loc', 'loc_rating', 'img', 'vid','img_url','vid_url','created_at','updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'user_id', 'user_email']

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

    def validate_title(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Title cannot be empty")
        return value.strip()

    def validate_desc(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Description cannot be empty")
        return value.strip()

    def validate_loc_rating(self, value):
        if value is not None and (value < 0 or value > 5):
            raise serializers.ValidationError("Location rating must be between 0 and 5")
        return value

    def validate_img(self, value):
        if value:
            if value.size > 10 * 1024 * 1024:
                raise serializers.ValidationError("Image size should not exceed 10MB")
            valid_extensions = ['jpg', 'jpeg', 'png', 'webp']
            ext = value.name.split('.')[-1].lower()
            if ext not in valid_extensions:
                raise serializers.ValidationError(
                    f"Invalid image format. Allowed formats: {', '.join(valid_extensions)}"
                )
        return value
    
    def validate_vid(self, value):
        if value:
            if value.size > 100 * 1024 * 1024:
                raise serializers.ValidationError("Video size should not exceed 100MB")
            valid_extensions = ['mp4', 'mov', 'avi', 'mkv', 'webm']
            ext = value.name.split('.')[-1].lower()
            if ext not in valid_extensions:
                raise serializers.ValidationError(
                    f"Invalid video format. Allowed formats: {', '.join(valid_extensions)}"
                )
        return value
