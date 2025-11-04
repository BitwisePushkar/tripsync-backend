import uuid
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

POST_REACTION_CHOICES = [
    ("love", "❤️ Love"),
    ("wow", "😮 Wow"),
    ("inspiring", "👏 Inspiring"),
    ("funny", "😂 Funny"),
    ("fire", "🔥 Fire"),
]

COMMENT_REACTION_CHOICES = [
    ("thumbs_up", "👍 Thumbs Up"),
    ("love", "❤️ Love"),
    ("funny", "😂 Funny"),
    ("hundred", "💯 Hundred"),
]

class Genre(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Post(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts", db_index=True)
    title = models.CharField(max_length=100)
    desc = models.TextField(max_length=2000)
    loc = models.CharField(max_length=100, blank=True, default="")
    rating = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(5)],)
    genres = models.ManyToManyField(Genre, related_name="posts", blank=True)
    share_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False,)
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]
        indexes  = [
            models.Index(fields=["-created"]),
            models.Index(fields=["user", "-created"]),
            models.Index(fields=["share_token"]),
        ]

    def __str__(self):
        return f"{self.title} by {self.user_id}"

class PostMedia(models.Model):
    MEDIA_TYPES = [
        ("image", "Image"),
        ("video", "Video"),
    ]
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="media")
    file_url = models.CharField(max_length=500)
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES)
    order = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created"]

    def __str__(self):
        return f"{self.media_type} for post {self.post_id}"

class PostReaction(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post_reactions")
    reaction_type = models.CharField(max_length=12, choices=POST_REACTION_CHOICES)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("post", "user")]
        indexes = [models.Index(fields=["post", "reaction_type"])]

    def __str__(self):
        return f"{self.user_id} → {self.reaction_type} on post {self.post_id}"

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    text = models.TextField(max_length=500)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created"]
        indexes  = [models.Index(fields=["post", "created"])]

    def __str__(self):
        return f"Comment by {self.user_id} on post {self.post_id}"

class CommentReaction(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comment_reactions")
    reaction_type = models.CharField(max_length=12, choices=COMMENT_REACTION_CHOICES)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("comment", "user")]
        indexes = [models.Index(fields=["comment", "reaction_type"])]

    def __str__(self):
        return f"{self.user_id} → {self.reaction_type} on comment {self.comment_id}"

class UserFollow(models.Model):
    follower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="following_set",)
    following = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="followers_set",)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("follower", "following")]
        indexes = [
            models.Index(fields=["follower", "created"]),
            models.Index(fields=["following", "created"]),
        ]

    def __str__(self):
        return f"{self.follower_id} → {self.following_id}"

class PostView(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="views")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post_views",)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("post", "user")]
        indexes = [models.Index(fields=["post"])]

    def __str__(self):
        return f"Post {self.post_id} viewed by user {self.user_id}"