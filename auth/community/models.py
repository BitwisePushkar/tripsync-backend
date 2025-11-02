from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

class Post(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=50)
    desc = models.CharField(max_length=1000)
    loc = models.CharField(max_length=75, blank=True, null=True)
    rating = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(5)])
    img = models.ImageField(upload_to='images/', blank=True, null=True)
    vid = models.FileField(upload_to='videos/', blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-created']
    def __str__(self):
        return self.title

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField(max_length=500)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-created']
    def __str__(self):
        return self.user.id + " commented on '" + self.post.title + "'"

class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='post_likes')
    like = models.BooleanField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    class Meta:
        unique_together = ('post', 'user')
        ordering = ['-created']
    def __str__(self):
        if self.like:
            return self.user.id + " liked the post '" + self.post.title + "'"
        else:
            return self.user.id + " disliked the post '" + self.post.title + "'"
