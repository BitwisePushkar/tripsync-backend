import logging
import uuid
from django.contrib.auth import get_user_model
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import CursorPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from community.models import (Post, PostReaction, Comment, CommentReaction, UserFollow, PostView, Genre, PostMedia,
    POST_REACTION_CHOICES, COMMENT_REACTION_CHOICES)
from community.serializers import (PostSerializer, PostDetailSerializer, PostCreateSerializer, PostUpdateSerializer,
    PostReactionInputSerializer, CommentSerializer, CommentReactionInputSerializer, FollowUserSerializer, GenreSerializer)
from personal.utils import upload_image_to_s3, delete_image_from_s3, extract_s3_key_from_url

User = get_user_model()
logger = logging.getLogger("community")

def _ok(message, data=None, code=status.HTTP_200_OK):
    body = {"status": "success", "message": message}
    if data is not None:
        body["data"] = data
    return Response(body, status=code)

def _err(message, errors=None, code=status.HTTP_400_BAD_REQUEST):
    body = {"status": "error", "message": message}
    if errors:
        body["errors"] = errors
    return Response(body, status=code)

def _post_queryset():
    return (
        Post.objects
        .select_related("user__profile")
        .prefetch_related(
            "genres",
            "media",
            Prefetch("reactions", queryset=PostReaction.objects.select_related("user")),
            Prefetch("comments",  queryset=Comment.objects.select_related("user__profile")),
        )
        .annotate(view_count=Count("views", distinct=True))
    )

class PostCursorPagination(CursorPagination):
    ordering = "-created"
    def get_ordering(self, request, queryset, view):
        return ("-created", "-id")
    page_size = 15
    page_size_query_param = "page_size"
    max_page_size = 50
    cursor_query_param = "cursor"

class CommentCursorPagination(CursorPagination):
    ordering = "created"
    def get_ordering(self, request, queryset, view):
        return ("created", "id")
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    cursor_query_param = "cursor"

class FollowCursorPagination(CursorPagination):
    ordering = "-id" 
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50
    cursor_query_param = "cursor"

def _upload_post_media(file_obj, post_id: int, media_type: str) -> tuple[bool, str]:
    ext = file_obj.name.rsplit(".", 1)[-1].lower()
    s3_key = f"community/{media_type}s/post_{post_id}_{uuid.uuid4().hex}.{ext}"
    return upload_image_to_s3(file_obj, s3_key, media_type=media_type)

@extend_schema(tags=["Community - Posts"])
class PostFeedView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Post feed (cursor-paginated, interest-sorted)",
        description="Returns posts newest-first with cursor pagination for infinite scroll.",
        parameters=[
            OpenApiParameter("genres", OpenApiTypes.STR, description="Comma-separated genre values. e.g. adventurous,nature"),
            OpenApiParameter("exclude_genres", OpenApiTypes.STR, description="Comma-separated genre values to exclude."),
            OpenApiParameter("user_id", OpenApiTypes.INT, description="Filter by user ID"),
            OpenApiParameter("search", OpenApiTypes.STR, description="Search title and description"),
            OpenApiParameter("cursor", OpenApiTypes.STR, description="Pagination cursor from previous response"),
            OpenApiParameter("page_size", OpenApiTypes.INT, description="Results per page (max 50, default 15)"),
            OpenApiParameter("feed", OpenApiTypes.STR, description="'all' (default) or 'following' — filter to users you follow"),
        ],
        responses={200: PostSerializer(many=True)},
    )
    def get(self, request):
        qs = _post_queryset()
        raw_genres = request.query_params.get("genres", "").strip()
        if raw_genres:
            requested_genres = [g.strip() for g in raw_genres.split(",") if g.strip()]
            if requested_genres:
                qs = qs.filter(genres__name__in=requested_genres).distinct()

        raw_exclude_genres = request.query_params.get("exclude_genres", "").strip()
        if raw_exclude_genres:
            excluded_genres = [g.strip() for g in raw_exclude_genres.split(",") if g.strip()]
            if excluded_genres:
                qs = qs.exclude(genres__name__in=excluded_genres).distinct()
        feed_mode = request.query_params.get("feed", "all")
        if feed_mode == "following":
            if not request.user.is_authenticated:
                return _err(
                    "Authentication required for following feed.",
                    code=status.HTTP_401_UNAUTHORIZED,
                )
            following_ids = UserFollow.objects.filter(
                follower=request.user
            ).values_list("following_id", flat=True)
            qs = qs.filter(user_id__in=following_ids)

        raw_uid = request.query_params.get("user_id", "").strip()
        if raw_uid:
            try:
                qs = qs.filter(user__id=int(raw_uid))
            except (ValueError, TypeError):
                return _err("user_id must be an integer.")
        q = request.query_params.get("search", "").strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(desc__icontains=q))
        paginator = PostCursorPagination()
        try:
            page = paginator.paginate_queryset(qs, request)
        except Exception:
            return _err("Invalid pagination cursor.", code=status.HTTP_400_BAD_REQUEST)
            
        serializer = PostSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

@extend_schema(tags=["Community - Posts"])
class PostCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        summary="Create a post",
        request=PostCreateSerializer,
        responses={
            201: PostSerializer,
            400: OpenApiResponse(description="Validation error"),
        },
        examples=[
            OpenApiExample(
                "Create post",
                value={
                    "title": "Sunrise at Kedarnath",
                    "desc": "The most spiritual sunrise I have ever witnessed.",
                    "loc": "Kedarnath, Uttarakhand",
                    "rating": 5,
                    "genre": "spiritual",
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        serializer = PostCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return _err("Validation failed.", errors=serializer.errors)
        data = serializer.validated_data
        genre_names = data.pop("genres", [])
        images = data.pop("images", [])
        videos = data.pop("videos", [])
        
        post = Post.objects.create(user=request.user, **data)
        
        if genre_names:
            genre_objs = [Genre.objects.get_or_create(name=name.lower().strip())[0] for name in genre_names]
            post.genres.set(genre_objs)

        for i, img_file in enumerate(images):
            success, result = _upload_post_media(img_file, post.pk, "img")
            if success:
                PostMedia.objects.create(post=post, file_url=result, media_type="image", order=i)

        for i, vid_file in enumerate(videos):
            success, result = _upload_post_media(vid_file, post.pk, "vid")
            if success:
                PostMedia.objects.create(post=post, file_url=result, media_type="video", order=len(images) + i)
        
        logger.info("Post %d created by user %d", post.pk, request.user.pk)
        return _ok(
            "Post created.",
            PostSerializer(post, context={"request": request}).data,
            code=status.HTTP_201_CREATED,
        )

@extend_schema(tags=["Community - Posts"])
class PostDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Get post detail",
        description="Returns full post with inline comments (first 20, oldest first).",
        responses={
            200: PostDetailSerializer,
            404: OpenApiResponse(description="Post not found"),
        },
    )
    def get(self, request, pk):
        post = get_object_or_404(
            Post.objects
            .select_related("user__profile")
            .prefetch_related(
                "genres",
                "media",
                Prefetch("reactions", queryset=PostReaction.objects.select_related("user")),
                Prefetch(
                    "comments",
                    queryset=(
                        Comment.objects
                        .select_related("user__profile")
                        .prefetch_related(
                            Prefetch("reactions", queryset=CommentReaction.objects.select_related("user"))
                        )
                        .order_by("created")
                    ),
                ),
            )
            .annotate(view_count=Count("views", distinct=True)),
            pk=pk,
        )
        return _ok("Post retrieved.", PostDetailSerializer(post, context={"request": request}).data)

@extend_schema(tags=["Community - Posts"])
class PostUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        summary="Update post",
        request=PostUpdateSerializer,
        responses={
            200: PostSerializer,
            403: OpenApiResponse(description="Not the post owner"),
            404: OpenApiResponse(description="Post not found"),
        },
    )
    def patch(self, request, pk):
        post = get_object_or_404(Post.objects.select_related("user"), pk=pk)
        if post.user_id != request.user.pk:
            return _err(
                "You can only edit your own posts.",
                code=status.HTTP_403_FORBIDDEN,
            )
        serializer = PostUpdateSerializer(data=request.data, partial=True, context={"post": post})
        if not serializer.is_valid():
            return _err("Validation failed.", errors=serializer.errors)
        data = serializer.validated_data
        genre_names = data.pop("genres", None)
        remove_all_media = data.pop("remove_all_media", False)
        images = data.pop("images", [])
        videos = data.pop("videos", [])
        
        if genre_names is not None:
            genre_objs = [Genre.objects.get_or_create(name=name.lower().strip())[0] for name in genre_names]
            post.genres.set(genre_objs)

        if remove_all_media:
            for m in post.media.all():
                key = extract_s3_key_from_url(m.file_url)
                if key: delete_image_from_s3(key)
            post.media.all().delete()
        if images or videos:
            last_order = post.media.count()
            for i, img_file in enumerate(images):
                success, result = _upload_post_media(img_file, post.pk, "img")
                if success:
                    PostMedia.objects.create(post=post, file_url=result, media_type="image", order=last_order + i)
            
            last_order = post.media.count()
            for i, vid_file in enumerate(videos):
                success, result = _upload_post_media(vid_file, post.pk, "vid")
                if success:
                    PostMedia.objects.create(post=post, file_url=result, media_type="video", order=last_order + i)

        for field, value in data.items():
            setattr(post, field, value)
        post.save()
        return _ok(
            "Post updated.",
            PostSerializer(post, context={"request": request}).data,
        )

@extend_schema(tags=["Community - Posts"])
class PostDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="Delete post",
        responses={
            200: OpenApiResponse(description="Post deleted"),
            403: OpenApiResponse(description="Not the post owner"),
            404: OpenApiResponse(description="Post not found"),
        },
    )
    def delete(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        if post.user_id != request.user.pk:
            return _err(
                "You can only delete your own posts.",
                code=status.HTTP_403_FORBIDDEN,
            )
        for m in post.media.all():
            key = extract_s3_key_from_url(m.file_url)
            if key:
                delete_image_from_s3(key)
        post.delete()
        logger.info("Post %d deleted by user %d", pk, request.user.pk)
        return _ok("Post deleted.")

@extend_schema(tags=["Community - Posts"])
class MyPostsView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="My posts",
        description="Returns the authenticated user's posts, newest first, cursor-paginated.",
        parameters=[
            OpenApiParameter("cursor", OpenApiTypes.STR, description="Pagination cursor"),
            OpenApiParameter("page_size", OpenApiTypes.INT, description="Results per page (max 50)"),
        ],
        responses={200: PostSerializer(many=True)},
    )
    def get(self, request):
        qs = _post_queryset().filter(user=request.user)
        paginator = PostCursorPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            PostSerializer(page, many=True, context={"request": request}).data
        )

@extend_schema(tags=["Community - Posts"])
class PostShareResolveView(APIView):
    permission_classes = [AllowAny]
    @extend_schema(
        summary="Resolve post share link",
        description="Resolve a share token to post data. Used by Kotlin App Links.",
        responses={
            200: PostSerializer,
            404: OpenApiResponse(description="Invalid share token"),
        },
    )
    def get(self, request, share_token):
        post = get_object_or_404(
            _post_queryset(),
            share_token=share_token,
        )
        return _ok("Post resolved.", PostSerializer(post, context={"request": request}).data)

@extend_schema(tags=["Community - Posts"])
class PostReactView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="React to a post",
        description="Add, change, or remove an emoji reaction on a post.",
        request=PostReactionInputSerializer,
        responses={
            200: OpenApiResponse(
                description="Reaction updated",
                examples=[
                    OpenApiExample(
                        "Reaction added",
                        value={
                            "status": "success",
                            "message": "Reaction added.",
                            "data": {
                                "action":    "added",
                                "reactions": {"love": 3, "wow": 1},
                            },
                        },
                    )
                ],
            ),
            400: OpenApiResponse(description="Invalid reaction type"),
            404: OpenApiResponse(description="Post not found"),
        },
        examples=[
            OpenApiExample("Love", value={"reaction_type": "love"}, request_only=True),
            OpenApiExample("Fire", value={"reaction_type": "fire"}, request_only=True),
        ],
    )
    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        serializer = PostReactionInputSerializer(data=request.data)
        if not serializer.is_valid():
            return _err("Invalid reaction.", errors=serializer.errors)
        reaction_type = serializer.validated_data["reaction_type"]
        existing = PostReaction.objects.filter(post=post, user=request.user).first()
        if existing:
            if existing.reaction_type == reaction_type:
                existing.delete()
                action = "removed"
            else:
                existing.reaction_type = reaction_type
                existing.save(update_fields=["reaction_type"])
                action = "changed"
        else:
            PostReaction.objects.create(post=post, user=request.user, reaction_type=reaction_type)
            action = "added"
        counts = {}
        for r in PostReaction.objects.filter(post=post):
            counts[r.reaction_type] = counts.get(r.reaction_type, 0) + 1
        return _ok(f"Reaction {action}.", {"action": action, "reactions": counts})

@extend_schema(tags=["Community - Comments"])
class CommentListView(APIView):
    permission_classes = [AllowAny]
    @extend_schema(
        summary="List comments",
        description="Returns comments for a post, oldest first.",
        parameters=[
            OpenApiParameter("cursor", OpenApiTypes.STR, description="Pagination cursor"),
            OpenApiParameter("page_size", OpenApiTypes.INT, description="Results per page (max 100, default 20)"),
        ],
        responses={200: CommentSerializer(many=True)},
    )
    def get(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        comments = (
            Comment.objects
            .filter(post=post)
            .select_related("user__profile")
            .prefetch_related(
                Prefetch("reactions", queryset=CommentReaction.objects.select_related("user"))
            )
            .order_by("created")
        )
        paginator = CommentCursorPagination()
        try:
            page = paginator.paginate_queryset(comments, request)
        except Exception:
            return _err("Invalid pagination cursor.", code=status.HTTP_400_BAD_REQUEST)
            
        return paginator.get_paginated_response(
            CommentSerializer(page, many=True, context={"request": request}).data
        )

@extend_schema(tags=["Community - Comments"])
class CommentCreateView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="Add a comment",
        request={
            "application/json": {
                "type": "object",
                "required": ["text"],
                "properties": {
                    "text": {"type": "string", "maxLength": 500, "example": "Absolutely stunning!"}
                },
            }
        },
        responses={
            201: CommentSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Post not found"),
        },
    )
    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        serializer = CommentSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return _err("Validation failed.", errors=serializer.errors)
        comment = Comment.objects.create(
            post=post,
            user=request.user,
            text=serializer.validated_data["text"],
        )
        return _ok(
            "Comment added.",
            CommentSerializer(comment, context={"request": request}).data,
            code=status.HTTP_201_CREATED,
        )

@extend_schema(tags=["Community - Comments"])
class CommentDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="Delete a comment",
        responses={
            200: OpenApiResponse(description="Comment deleted"),
            403: OpenApiResponse(description="Not the comment owner"),
            404: OpenApiResponse(description="Comment not found"),
        },
    )
    def delete(self, request, pk):
        comment = get_object_or_404(Comment, pk=pk)
        if comment.user_id != request.user.pk:
            return _err(
                "You can only delete your own comments.",
                code=status.HTTP_403_FORBIDDEN,
            )
        comment.delete()
        return _ok("Comment deleted.")

@extend_schema(tags=["Community - Comments"])
class CommentReactView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="React to a comment",
        description="Add, change, or remove a reaction on a comment.\n\nValid types: `thumbs_up` · `love` · `funny` · `hundred`",
        request=CommentReactionInputSerializer,
        responses={
            200: OpenApiResponse(description="Reaction updated"),
            400: OpenApiResponse(description="Invalid reaction type"),
            404: OpenApiResponse(description="Comment not found"),
        },
    )
    def post(self, request, pk):
        comment = get_object_or_404(Comment, pk=pk)
        serializer = CommentReactionInputSerializer(data=request.data)
        if not serializer.is_valid():
            return _err("Invalid reaction.", errors=serializer.errors)
        reaction_type = serializer.validated_data["reaction_type"]
        existing = CommentReaction.objects.filter(
            comment=comment, user=request.user
        ).first()
        if existing:
            if existing.reaction_type == reaction_type:
                existing.delete()
                action = "removed"
            else:
                existing.reaction_type = reaction_type
                existing.save(update_fields=["reaction_type"])
                action = "changed"
        else:
            CommentReaction.objects.create(
                comment=comment, user=request.user, reaction_type=reaction_type
            )
            action = "added"
        counts = {}
        for r in CommentReaction.objects.filter(comment=comment):
            counts[r.reaction_type] = counts.get(r.reaction_type, 0) + 1
        return _ok(f"Reaction {action}.", {"action": action, "reactions": counts})

@extend_schema(tags=["Community - Posts"])
class PostViewRecordView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="Record a post view",
        description="Record that the user has viewed this post.",
        responses={
            200: OpenApiResponse(
                description="View recorded or already recorded",
                examples=[
                    OpenApiExample(
                        "New view",
                        value={"status": "success", "message": "View recorded.", "data": {"view_count": 42}},
                    ),
                    OpenApiExample(
                        "Already viewed",
                        value={"status": "success", "message": "Already viewed.", "data": {"view_count": 42}},
                    ),
                ],
            ),
            404: OpenApiResponse(description="Post not found"),
        },
    )
    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        if post.user_id == request.user.pk:
            view_count = PostView.objects.filter(post=post).count()
            return _ok("View not counted for own post.", {"view_count": view_count})
        _, created = PostView.objects.get_or_create(post=post, user=request.user)
        view_count = PostView.objects.filter(post=post).count()
        message = "View recorded." if created else "Already viewed."
        return _ok(message, {"view_count": view_count})

@extend_schema(tags=["Community - Follow"])
class FollowToggleView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="Follow or unfollow a user",
        description="Toggle follow state for another user.",
        responses={
            200: OpenApiResponse(
                description="Follow state toggled",
                examples=[
                    OpenApiExample(
                        "Followed",
                        value={
                            "status": "success",
                            "message": "You are now following this user.",
                            "data": {
                                "action": "followed",
                                "followers_count": 42,
                            },
                        },
                    ),
                    OpenApiExample(
                        "Unfollowed",
                        value={
                            "status": "success",
                            "message": "You have unfollowed this user.",
                            "data": {
                                "action": "unfollowed",
                                "followers_count": 41,
                            },
                        },
                    ),
                ],
            ),
            400: OpenApiResponse(description="Cannot follow yourself"),
            404: OpenApiResponse(description="User not found"),
        },
    )
    def post(self, request, user_id):
        if user_id == request.user.pk:
            return _err("You cannot follow yourself.")
        target = get_object_or_404(
            User.objects.select_related("profile"),
            pk=user_id,
            is_active=True,
        )
        existing = UserFollow.objects.filter(
            follower=request.user, following=target
        ).first()
        if existing:
            existing.delete()
            action = "unfollowed"
            message = "You have unfollowed this user."
        else:
            UserFollow.objects.create(follower=request.user, following=target)
            action = "followed"
            message = "You are now following this user."
        followers_count = UserFollow.objects.filter(following=target).count()
        logger.info("User %d %s user %d", request.user.pk, action, target.pk)
        return _ok(message, {"action": action, "followers_count": followers_count})

@extend_schema(tags=["Community - Follow"])
class FollowerListView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="List followers",
        description="Returns users who follow the specified user, newest first.",
        parameters=[
            OpenApiParameter("cursor", OpenApiTypes.STR, description="Pagination cursor"),
            OpenApiParameter("page_size", OpenApiTypes.INT, description="Results per page (max 50, default 20)"),
        ],
        responses={200: FollowUserSerializer(many=True)},
    )
    def get(self, request, user_id):
        target = get_object_or_404(User, pk=user_id, is_active=True)
        followers = (
            User.objects
            .filter(following_set__following=target)
            .select_related("profile")
            .annotate(
                followers_count=Count("followers_set", distinct=True),
                following_count=Count("following_set", distinct=True),
            )
            .order_by("-following_set__created")
        )
        request._following_ids = set(
            UserFollow.objects.filter(follower=request.user)
            .values_list("following_id", flat=True)
        )
        paginator = FollowCursorPagination()
        try:
            page = paginator.paginate_queryset(followers, request)
        except Exception:
            return _err("Invalid pagination cursor.", code=status.HTTP_400_BAD_REQUEST)
            
        return paginator.get_paginated_response(
            FollowUserSerializer(page, many=True, context={"request": request}).data
        )

@extend_schema(tags=["Community - Follow"])
class FollowingListView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="List following",
        description="Returns users that the specified user follows, newest first.",
        parameters=[
            OpenApiParameter("cursor", OpenApiTypes.STR, description="Pagination cursor"),
            OpenApiParameter("page_size", OpenApiTypes.INT, description="Results per page (max 50, default 20)"),
        ],
        responses={200: FollowUserSerializer(many=True)},
    )
    def get(self, request, user_id):
        target = get_object_or_404(User, pk=user_id, is_active=True)
        following = (
            User.objects
            .filter(followers_set__follower=target)
            .select_related("profile")
            .annotate(
                followers_count=Count("followers_set", distinct=True),
                following_count=Count("following_set", distinct=True),
            )
            .order_by("-followers_set__created")
        )
        request._following_ids = set(
            UserFollow.objects.filter(follower=request.user)
            .values_list("following_id", flat=True)
        )
        paginator = FollowCursorPagination()
        try:
            page = paginator.paginate_queryset(following, request)
        except Exception:
            return _err("Invalid pagination cursor.", code=status.HTTP_400_BAD_REQUEST)
            
        return paginator.get_paginated_response(
            FollowUserSerializer(page, many=True, context={"request": request}).data
        )

@extend_schema(tags=["Community - Follow"])
class UserProfileStatsView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="Get user profile stats",
        description="Returns public stats for a user's profile page header",
        responses={
            200: OpenApiResponse(
                description="Profile stats",
                examples=[
                    OpenApiExample(
                        "Stats",
                        value={
                            "status": "success",
                            "data": {
                                "user_id": 5,
                                "email": "priya@example.com",
                                "fname": "Priya",
                                "lname": "Singhal",
                                "profile_pic": "https://...",
                                "post_count": 12,
                                "followers_count": 230,
                                "following_count": 45,
                                "is_following": True,
                            },
                        },
                    )
                ],
            ),
            404: OpenApiResponse(description="User not found"),
        },
    )
    def get(self, request, user_id):
        target = get_object_or_404(
            User.objects
            .select_related("profile")
            .annotate(
                post_count=Count("posts", distinct=True),
                followers_count=Count("followers_set", distinct=True),
                following_count=Count("following_set", distinct=True),
            ),
            pk=user_id,
            is_active=True,
        )
        is_following = UserFollow.objects.filter(
            follower=request.user, following=target
        ).exists()
        profile = getattr(target, "profile", None)
        return _ok("Profile stats retrieved.", {
            "user_id": target.pk,
            "email": target.email,
            "fname": profile.fname if profile else "",
            "lname": profile.lname if profile else "",
            "profile_pic": profile.profile_pic if profile else "",
            "post_count": target.post_count,
            "followers_count": target.followers_count,
            "following_count": target.following_count,
            "is_following": is_following,
        })