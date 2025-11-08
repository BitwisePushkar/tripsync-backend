from rest_framework import serializers
from .models import Post, Comment, PostLike
from django.conf import settings
from personal.models import Profile

class PostSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    img_url = serializers.SerializerMethodField()
    vid_url = serializers.SerializerMethodField()
    likes = serializers.SerializerMethodField()
    dislikes = serializers.SerializerMethodField()
    total_comments = serializers.SerializerMethodField()
    reaction = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ['id', 'user', 'title', 'desc', 'loc', 'rating', 'img', 'vid', 'img_url', 'vid_url', 'likes', 'dislikes', 'total_comments', 'reaction', 'owner', 'created', 'updated']
        read_only_fields = ['id', 'created', 'updated']

    def get_user(self, obj):
        if hasattr(obj.user, 'profile'):
            return UserMiniSerializer(obj.user.profile, context=self.context).data
        return None

    def get_img_url(self, obj):
        if obj.img:
            if hasattr(settings, 'USE_S3') and settings.USE_S3:
                return obj.img.url  
            else:
                req = self.context.get('request')
                if req:
                    return req.build_absolute_uri(obj.img.url)
                return obj.img.url
            return None

    def get_vid_url(self, obj):
        if obj.vid:
            if hasattr(settings, 'USE_S3') and settings.USE_S3:
                return obj.vid.url  
            else:
                req = self.context.get('request')
                if req:
                    return req.build_absolute_uri(obj.vid.url)
                return obj.vid.url
        return None
    
    def get_likes(self, obj):
        return obj.likes.filter(like=True).count()
    
    def get_dislikes(self, obj):
        return obj.likes.filter(like=False).count()
    
    def get_total_comments(self, obj):
        return obj.comments.count()

    def get_reaction(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        reaction = PostLike.objects.filter(post=obj, user=request.user).first()
        if reaction:
            return "like" if reaction.like else "dislike"       
        return None
   
    def get_owner(self, obj):
        req = self.context.get('request')
        if req and req.user.is_authenticated:
            return obj.user == req.user
        return False

    def validate_title(self, val):
        if not val or not val.strip():
            raise serializers.ValidationError("Title cannot be empty")
        return val.strip()

    def validate_desc(self, val):
        if not val or not val.strip():
            raise serializers.ValidationError("Description cannot be empty")
        return val.strip()

    def validate_rating(self, val):
        if val is not None and (val < 0 or val > 5):
            raise serializers.ValidationError("Rating must be between 0 and 5")
        return val

    def validate_img(self, val):
        if val:
            if val.size > 5 * 1024 * 1024:
                raise serializers.ValidationError("Image size should not be more than 5MB")
            if val.name.split('.')[-1].lower() not in ['jpg', 'jpeg', 'png', 'webp']:
                raise serializers.ValidationError("Only JPG, JPEG, PNG, and WEBP formats are allowed")
        return val
    
    def validate_vid(self, val):
        if val:
            if val.size > 100 * 1024 * 1024:
                raise serializers.ValidationError("Video size should not be more than 100MB")
            if val.name.split('.')[-1].lower() not in ['mp4', 'mov', 'avi', 'mkv', 'webm']:
                raise serializers.ValidationError("Only MP4, MOV, AVI, MKV, and WEBM formats are allowed")
        return val

class UserMiniSerializer(serializers.ModelSerializer):
    uid = serializers.IntegerField(source='user.id', read_only=True)
    pic = serializers.SerializerMethodField()    
    class Meta:
        model = Profile
        fields = ['uid', 'fname', 'lname', 'pic']    
    def get_pic(self, obj):
        if obj.profile_pic:
            req = self.context.get('request')
            if req:
                return req.build_absolute_uri(obj.profile_pic.url)
            return obj.profile_pic.url
        return None


class CommentSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()
    class Meta:
        model = Comment
        fields = ['id', 'post', 'user', 'text', 'owner', 'created', 'updated']
        read_only_fields = ['id', 'post', 'created', 'updated']
    def get_user(self, obj):
        if hasattr(obj.user, 'profile'):
            return UserMiniSerializer(obj.user.profile, context=self.context).data
        return None
    def get_owner(self, obj):
        req = self.context.get('request')
        if req and req.user.is_authenticated:
            return obj.user == req.user
        return False
    def validate_text(self, val):
        if not val or not val.strip() or len(val.strip()) > 500:
            raise serializers.ValidationError("Comment must not be empty and cannot exceed 500 characters")
        return val.strip()

class PostDetailSerializer(PostSerializer):
    comments = CommentSerializer(many=True, read_only=True)   
    class Meta(PostSerializer.Meta):
        fields = PostSerializer.Meta.fields + ['comments']