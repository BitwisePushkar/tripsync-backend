from django.contrib import admin
from .models import Post, Comment, PostLike

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display  = ['id', 'title', 'user', 'loc', 'rating', 'created']
    list_filter   = ['rating', 'created']
    search_fields = ['title', 'desc', 'user__email']
    readonly_fields = ['created', 'updated']
    ordering = ['-created']

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display  = ['id', 'user', 'post', 'created']
    search_fields = ['text', 'user__email', 'post__title']
    readonly_fields = ['created', 'updated']
    ordering = ['-created']

@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display  = ['id', 'user', 'post', 'like', 'created']
    list_filter   = ['like']
    search_fields = ['user__email', 'post__title']
    readonly_fields = ['created', 'updated']