from django.contrib import admin
from community.models import Post, PostReaction, Comment, CommentReaction, UserFollow, PostView, Genre, PostMedia

class PostMediaInline(admin.TabularInline):
    model = PostMedia
    extra = 0

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["name"]

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "user", "get_genres", "media_count", "rating", "created"]
    list_filter = ["genres", "rating", "created"]
    search_fields = ["title", "desc", "user__email"]
    readonly_fields = ["created", "updated", "share_token"]
    inlines = [PostMediaInline]
    ordering = ["-created"]

    def get_genres(self, obj):
        return ", ".join([g.name for g in obj.genres.all()])
    get_genres.short_description = "Genres"

    def media_count(self, obj):
        return obj.media.count()
    media_count.short_description = "Media Count"

@admin.register(PostReaction)
class PostReactionAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "post", "reaction_type", "created"]
    list_filter = ["reaction_type"]
    search_fields = ["user__email", "post__title"]
    readonly_fields = ["created"]

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "post", "text_preview", "created"]
    search_fields = ["text", "user__email", "post__title"]
    readonly_fields = ["created", "updated"]
    ordering = ["-created"]

    def text_preview(self, obj):
        return obj.text[:60]
    text_preview.short_description = "Text"

@admin.register(CommentReaction)
class CommentReactionAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "comment", "reaction_type", "created"]
    list_filter = ["reaction_type"]
    search_fields = ["user__email"]
    readonly_fields = ["created"]

@admin.register(UserFollow)
class UserFollowAdmin(admin.ModelAdmin):
    list_display = ["id", "follower", "following", "created"]
    search_fields = ["follower__email", "following__email"]
    readonly_fields = ["created"]
    ordering = ["-created"]

@admin.register(PostView)
class PostViewAdmin(admin.ModelAdmin):
    list_display = ["id", "post", "user", "viewed_at"]
    search_fields = ["user__email", "post__title"]
    readonly_fields = ["viewed_at"]
    ordering = ["-viewed_at"]