from rest_framework import serializers
from django.contrib.auth import get_user_model
from community.models import (
    Post, PostReaction, Comment, CommentReaction, Genre, UserFollow, PostMedia,
    POST_REACTION_CHOICES, COMMENT_REACTION_CHOICES,
)

User = get_user_model()

class AuthorSerializer(serializers.ModelSerializer):
    fname = serializers.SerializerMethodField()
    lname = serializers.SerializerMethodField()
    profile_pic = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "fname", "lname", "profile_pic"]
        read_only_fields = fields

    def get_fname(self, obj):
        p = getattr(obj, "profile", None)
        return p.fname if p else ""

    def get_lname(self, obj):
        p = getattr(obj, "profile", None)
        return p.lname if p else ""

    def get_profile_pic(self, obj):
        p = getattr(obj, "profile", None)
        return p.profile_pic if p else ""

class CommentReactionInputSerializer(serializers.Serializer):
    reaction_type = serializers.ChoiceField(
        choices=[c[0] for c in COMMENT_REACTION_CHOICES],
    )

class CommentSerializer(serializers.ModelSerializer):
    user = AuthorSerializer(read_only=True)
    reactions = serializers.SerializerMethodField()
    my_reaction = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()

    class Meta:
        model  = Comment
        fields = [
            "id", "post", "user", "text",
            "reactions", "my_reaction", "owner",
            "created", "updated",
        ]
        read_only_fields = ["id", "post", "user", "reactions", "my_reaction", "owner", "created", "updated"]

    def get_reactions(self, obj):
        counts = {}
        for r in obj.reactions.all():
            counts[r.reaction_type] = counts.get(r.reaction_type, 0) + 1
        return counts

    def get_my_reaction(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        for r in obj.reactions.all():
            if r.user_id == request.user.pk:
                return r.reaction_type
        return None

    def get_owner(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.user_id == request.user.pk
        return False

    def validate_text(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Comment cannot be empty.")
        if len(value.strip()) > 500:
            raise serializers.ValidationError("Comment cannot exceed 500 characters.")
        return value.strip()

class PostReactionInputSerializer(serializers.Serializer):
    reaction_type = serializers.ChoiceField(
        choices=[c[0] for c in POST_REACTION_CHOICES],
    )

class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ["id", "name"]

class PostMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostMedia
        fields = ["id", "file_url", "media_type", "order"]

class PostSerializer(serializers.ModelSerializer):
    user = AuthorSerializer(read_only=True)
    genres = GenreSerializer(many=True, read_only=True)
    media = PostMediaSerializer(many=True, read_only=True)
    reactions = serializers.SerializerMethodField()
    my_reaction = serializers.SerializerMethodField()
    total_comments = serializers.SerializerMethodField()
    view_count = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()
    share_url = serializers.SerializerMethodField()

    class Meta:
        model  = Post
        fields = [
            "id", "user", "title", "desc", "loc", "rating", "genres", "media",
            "reactions", "my_reaction", "total_comments","view_count",
            "owner", "share_url",
            "created", "updated",
        ]
        read_only_fields = [
            "id", "user", "media", "reactions", "my_reaction",
            "total_comments", "view_count","owner", "share_url",
            "created", "updated",
        ]

    def get_reactions(self, obj):
        counts = {}
        for r in obj.reactions.all():
            counts[r.reaction_type] = counts.get(r.reaction_type, 0) + 1
        return counts

    def get_my_reaction(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        for r in obj.reactions.all():
            if r.user_id == request.user.pk:
                return r.reaction_type
        return None

    def get_total_comments(self, obj):
        return len(obj.comments.all())

    def get_owner(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.user_id == request.user.pk
        return False

    def get_share_url(self, obj):
        return f"https://tripsync.com/share/post/{obj.share_token}/"

    def get_view_count(self, obj):
        return getattr(obj, "view_count", obj.views.count())

class PostDetailSerializer(PostSerializer):
    comments = CommentSerializer(many=True, read_only=True)

    class Meta(PostSerializer.Meta):
        fields = PostSerializer.Meta.fields + ["comments"]

class PostCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=100)
    desc = serializers.CharField(max_length=2000)
    loc = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    rating = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=5)
    genres = serializers.ListField(child=serializers.CharField(max_length=50), required=False, default=list)
    images = serializers.ListField(child=serializers.ImageField(), required=False)
    videos = serializers.ListField(child=serializers.FileField(), required=False)

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("Title cannot be empty.")
        return value.strip()

    def validate_desc(self, value):
        if not value.strip():
            raise serializers.ValidationError("Description cannot be empty.")
        return value.strip()

    def validate_images(self, value):
        for img in value:
            if img.size > 5 * 1024 * 1024:
                raise serializers.ValidationError(f"Image {img.name} must be smaller than 5MB.")
            ext = img.name.rsplit(".", 1)[-1].lower()
            if ext not in ["jpg", "jpeg", "png", "webp"]:
                raise serializers.ValidationError(f"Image {img.name}: Allowed formats: jpg, jpeg, png, webp.")
        return value

    def validate_videos(self, value):
        for vid in value:
            if vid.size > 100 * 1024 * 1024:
                raise serializers.ValidationError(f"Video {vid.name} must be smaller than 100MB.")
            ext = vid.name.rsplit(".", 1)[-1].lower()
            if ext not in ["mp4", "mov", "avi", "mkv", "webm"]:
                raise serializers.ValidationError(f"Video {vid.name}: Allowed formats: mp4, mov, avi, mkv, webm.")
        return value

    def validate(self, data):
        total_media = len(data.get("images", [])) + len(data.get("videos", []))
        if total_media > 6:
            raise serializers.ValidationError("Maximum 6 media files allowed per post.")
        return data

class PostUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=100, required=False)
    desc = serializers.CharField(max_length=2000, required=False)
    loc = serializers.CharField(max_length=100, required=False, allow_blank=True)
    rating = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=5)
    genres = serializers.ListField(child=serializers.CharField(max_length=50), required=False)
    images = serializers.ListField(child=serializers.ImageField(), required=False)
    videos = serializers.ListField(child=serializers.FileField(), required=False)
    remove_all_media = serializers.BooleanField(required=False, default=False)

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("Title cannot be empty.")
        return value.strip()

    def validate_desc(self, value):
        if not value.strip():
            raise serializers.ValidationError("Description cannot be empty.")
        return value.strip()

    def validate_images(self, value):
        for img in value:
            if img.size > 5 * 1024 * 1024:
                raise serializers.ValidationError(f"Image {img.name} must be smaller than 5MB.")
            ext = img.name.rsplit(".", 1)[-1].lower()
            if ext not in ["jpg", "jpeg", "png", "webp"]:
                raise serializers.ValidationError(f"Image {img.name}: Allowed formats: jpg, jpeg, png, webp.")
        return value

    def validate_videos(self, value):
        for vid in value:
            if vid.size > 100 * 1024 * 1024:
                raise serializers.ValidationError(f"Video {vid.name} must be smaller than 100MB.")
            ext = vid.name.rsplit(".", 1)[-1].lower()
            if ext not in ["mp4", "mov", "avi", "mkv", "webm"]:
                raise serializers.ValidationError(f"Video {vid.name}: Allowed formats: mp4, mov, avi, mkv, webm.")
        return value

    def validate(self, data):
        if data.get("remove_all_media") and (data.get("images") or data.get("videos")):
            raise serializers.ValidationError("Cannot remove all media and upload new media at the same time.")
        
        # Enforce total limit of 6
        post = self.context.get("post")
        if post and not data.get("remove_all_media"):
            current_count = post.media.count()
            new_count = len(data.get("images", [])) + len(data.get("videos", []))
            if current_count + new_count > 6:
                raise serializers.ValidationError(f"Maximum 6 media files allowed. Post already has {current_count}.")
        
        return data

class FollowUserSerializer(serializers.ModelSerializer):
    fname = serializers.SerializerMethodField()
    lname = serializers.SerializerMethodField()
    profile_pic = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            "id", "email", "fname", "lname", "profile_pic",
            "followers_count", "following_count", "is_following",
        ]
        read_only_fields = fields

    def _profile(self, obj):
        return getattr(obj, "profile", None)

    def get_fname(self, obj):
        p = self._profile(obj)
        return p.fname if p else ""

    def get_lname(self, obj):
        p = self._profile(obj)
        return p.lname if p else ""

    def get_profile_pic(self, obj):
        p = self._profile(obj)
        return p.profile_pic if p else ""

    def get_followers_count(self, obj):
        return getattr(obj, "followers_count", obj.followers_set.count())

    def get_following_count(self, obj):
        return getattr(obj, "following_count", obj.following_set.count())

    def get_is_following(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        
        # Optimized lookup if view pre-calculated it
        following_ids = getattr(request, "_following_ids", None)
        if following_ids is not None:
            return obj.pk in following_ids

        return UserFollow.objects.filter(follower=request.user, following=obj).exists()