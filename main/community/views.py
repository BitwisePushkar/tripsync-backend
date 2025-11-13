from rest_framework.views import APIView
from rest_framework import status, parsers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from .models import Post, Comment, PostLike
from .serializers import PostSerializer, PostDetailSerializer, CommentSerializer

class PostListView(APIView):
    permission_classes = [AllowAny]
    @extend_schema(
        tags=['Posts'],
        summary='List all posts',
        description=(
            "Returns all posts. Optional filters:\n\n"
        ),
        parameters=[
            OpenApiParameter(name='user', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, description='Filter by user ID', required=False),
            OpenApiParameter(name='search', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, description='Search posts by title (case-insensitive)', required=False),
        ],
        responses={
            200: OpenApiResponse(
                description='Posts retrieved',
                examples=[
                    OpenApiExample(
                        name='Success',
                        value={
                            "status": "success",
                            "count": 2,
                            "data": [
                                {
                                    "id": 1, "title": "Trip to Paris", "desc": "Visited Eiffel Tower",
                                    "loc": "Paris, France", "rating": 5,
                                    "img_url": "https://cdn.example.com/images/paris.jpg", "vid_url": None,
                                    "likes": 10, "dislikes": 1, "total_comments": 3,
                                    "reaction": None, "owner": False,
                                    "user": {"uid": 2, "fname": "John", "lname": "Doe", "pic": None},
                                    "created": "2024-01-15T10:30:00Z", "updated": "2024-01-15T10:30:00Z"
                                },
                                {
                                    "id": 2, "title": "Hiking in Manali", "desc": "Snow adventure!",
                                    "loc": "Manali, India", "rating": 4,
                                    "img_url": None, "vid_url": None,
                                    "likes": 5, "dislikes": 0, "total_comments": 1,
                                    "reaction": "like", "owner": True,
                                    "user": {"uid": 1, "fname": "Jane", "lname": "Smith", "pic": None},
                                    "created": "2024-01-14T08:00:00Z", "updated": "2024-01-14T08:00:00Z"
                                }
                            ]
                        },
                        response_only=True,
                    )
                ]
            )
        }
    )
    def get(self, req):
        posts = Post.objects.select_related('user__profile').prefetch_related('likes', 'comments').all()
        uid = req.query_params.get('user')
        if uid:
            try:
                posts = posts.filter(user__id=int(uid))
            except (ValueError, TypeError):
                pass
        q = req.query_params.get('search', '').strip()
        if q:
            posts = posts.filter(title__icontains=q)
        s = PostSerializer(posts, many=True, context={'request': req})
        return Response({'status': 'success', 'count': posts.count(), 'data': s.data})

class PostCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    @extend_schema(
        tags=['Posts'],
        summary='Create a new post',
        description=(
            "Creates a new post for the authenticated user.\n\n"
        ),
        request={
            'multipart/form-data': {
                'type': 'object',
                'required': ['title', 'desc'],
                'properties': {
                    'title':  {'type': 'string', 'example': 'Sunset at Bali', 'maxLength': 50},
                    'desc':   {'type': 'string', 'example': 'Beautiful beach view!', 'maxLength': 1000},
                    'loc':    {'type': 'string', 'example': 'Bali, Indonesia', 'maxLength': 75},
                    'rating': {'type': 'integer', 'example': 5, 'minimum': 0, 'maximum': 5},
                    'img':    {'type': 'string', 'format': 'binary', 'description': 'Optional image · max 5MB'},
                    'vid':    {'type': 'string', 'format': 'binary', 'description': 'Optional video · max 100MB'},
                }
            }
        },
        responses={
            201: OpenApiResponse(
                description='Post created',
                examples=[
                    OpenApiExample(
                        name='Success',
                        value={
                            "status": "success",
                            "message": "Post created successfully",
                            "data": {
                                "id": 5, "title": "Sunset at Bali", "desc": "Beautiful beach view!",
                                "loc": "Bali, Indonesia", "rating": 5,
                                "img_url": "https://cdn.example.com/images/bali.jpg", "vid_url": None,
                                "likes": 0, "dislikes": 0, "total_comments": 0,
                                "reaction": None, "owner": True,
                                "user": {"uid": 1, "fname": "John", "lname": "Doe", "pic": None},
                                "created": "2024-01-15T10:30:00Z", "updated": "2024-01-15T10:30:00Z"
                            }
                        },
                        response_only=True,
                    )
                ]
            ),
            400: OpenApiResponse(
                description='Validation error',
                examples=[
                    OpenApiExample(
                        name='Error — Missing Title',
                        value={"title": ["Title cannot be empty"]},
                        response_only=True,
                    ),
                    OpenApiExample(
                        name='Error — Image Too Large',
                        value={"img": ["Image size must not exceed 5MB"]},
                        response_only=True,
                    ),
                    OpenApiExample(
                        name='Error — Bad Rating',
                        value={"rating": ["Rating must be between 0 and 5"]},
                        response_only=True,
                    ),
                ]
            ),
        }
    )
    def post(self, req):
        s = PostSerializer(data=req.data, context={'request': req})
        s.is_valid(raise_exception=True)
        s.save(user=req.user)
        return Response({'status': 'success', 'message': 'Post created successfully', 'data': s.data},status=status.HTTP_201_CREATED)

class PostDetailView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        tags=['Posts'],
        summary='Get post details',
        description='Returns full post details including all comments. No authentication required.',
        responses={
            200: OpenApiResponse(
                description='Post retrieved',
                examples=[
                    OpenApiExample(
                        name='Success',
                        value={
                            "status": "success",
                            "data": {
                                "id": 1, "title": "Trip to Paris", "desc": "Visited Eiffel Tower",
                                "loc": "Paris, France", "rating": 5,
                                "img_url": "https://cdn.example.com/images/paris.jpg", "vid_url": None,
                                "likes": 10, "dislikes": 1, "total_comments": 2,
                                "reaction": None, "owner": False,
                                "user": {"uid": 2, "fname": "John", "lname": "Doe", "pic": None},
                                "comments": [
                                    {
                                        "id": 10, "post": 1, "text": "Looks amazing!",
                                        "owner": False, "created": "2024-01-15T11:00:00Z", "updated": "2024-01-15T11:00:00Z",
                                        "user": {"uid": 3, "fname": "Alex", "lname": "Kim", "pic": None}
                                    }
                                ],
                                "created": "2024-01-15T10:30:00Z", "updated": "2024-01-15T10:30:00Z"
                            }
                        },
                        response_only=True,
                    )
                ]
            ),
            404: OpenApiResponse(
                description='Post not found',
                examples=[
                    OpenApiExample(
                        name='Error',
                        value={"detail": "No Post matches the given query."},
                        response_only=True,
                    )
                ]
            ),
        }
    )
    def get(self, req, pk):
        p = get_object_or_404(Post.objects.select_related('user__profile')
                              .prefetch_related('likes', 'comments__user__profile'),pk=pk)
        s = PostDetailSerializer(p, context={'request': req})
        return Response({'status': 'success', 'data': s.data})

class PostUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    @extend_schema(
        tags=['Posts'],
        summary='Update a post',
        description=(
            "Partially updates your own post. All fields are optional.\n\n"
        ),
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'title':  {'type': 'string', 'example': 'Updated Bali Post'},
                    'desc':   {'type': 'string', 'example': 'New description'},
                    'loc':    {'type': 'string', 'example': 'Bali, Indonesia'},
                    'rating': {'type': 'integer', 'example': 4},
                    'img':    {'type': 'string', 'format': 'binary'},
                    'vid':    {'type': 'string', 'format': 'binary'},
                }
            }
        },
        responses={
            200: OpenApiResponse(
                description='Post updated',
                examples=[
                    OpenApiExample(
                        name='Success',
                        value={
                            "status": "success",
                            "message": "Post updated successfully",
                            "data": {"id": 5, "title": "Updated Bali Post", "desc": "New description"}
                        },
                        response_only=True,
                    )
                ]
            ),
            403: OpenApiResponse(
                description='Not the post owner',
                examples=[
                    OpenApiExample(
                        name='Error — Forbidden',
                        value={
                            "status": "error",
                            "message": "Permission denied",
                            "errors": {"permission": ["You can only edit your own posts"]}
                        },
                        response_only=True,
                    )
                ]
            ),
            404: OpenApiResponse(
                description='Post not found',
                examples=[
                    OpenApiExample(
                        name='Error',
                        value={"detail": "No Post matches the given query."},
                        response_only=True,
                    )
                ]
            ),
        }
    )
    def patch(self, req, pk):
        p = get_object_or_404(Post, pk=pk)
        if p.user != req.user:
            return Response({'status': 'error', 'message': 'Permission denied', 'errors': {'permission': ['You can only edit your own posts']}},status=status.HTTP_403_FORBIDDEN)
        s = PostSerializer(p, data=req.data, partial=True, context={'request': req})
        s.is_valid(raise_exception=True)
        s.save()
        return Response({'status': 'success', 'message': 'Post updated successfully', 'data': s.data})

class PostDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Posts'],
        summary='Delete a post',
        description='Permanently deletes your own post including all its comments and likes.',
        responses={
            200: OpenApiResponse(
                description='Post deleted',
                examples=[
                    OpenApiExample(
                        name='Success',
                        value={"status": "success", "message": "Post deleted successfully"},
                        response_only=True,
                    )
                ]
            ),
            403: OpenApiResponse(
                description='Not the post owner',
                examples=[
                    OpenApiExample(
                        name='Error — Forbidden',
                        value={
                            "status": "error",
                            "message": "Permission denied",
                            "errors": {"permission": ["You can only delete your own posts"]}
                        },
                        response_only=True,
                    )
                ]
            ),
            404: OpenApiResponse(
                description='Post not found',
                examples=[
                    OpenApiExample(
                        name='Error',
                        value={"detail": "No Post matches the given query."},
                        response_only=True,
                    )
                ]
            ),
        }
    )
    def delete(self, req, pk):
        p = get_object_or_404(Post, pk=pk)
        if p.user != req.user:
            return Response({'status': 'error', 'message': 'Permission denied', 'errors': {'permission': ['You can only delete your own posts']}},status=status.HTTP_403_FORBIDDEN)
        p.delete()
        return Response({'status': 'success', 'message': 'Post deleted successfully'}, status=status.HTTP_200_OK)

class MyPostsView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        tags=['Posts'],
        summary='My posts',
        description='Returns all posts created by the currently authenticated user.',
        responses={
            200: OpenApiResponse(
                description='My posts retrieved',
                examples=[
                    OpenApiExample(
                        name='Success',
                        value={
                            "status": "success",
                            "count": 2,
                            "data": [
                                {"id": 10, "title": "Sunset in Bali", "desc": "Beautiful!", "likes": 3, "dislikes": 0, "total_comments": 1, "owner": True},
                                {"id": 12, "title": "Paris Vlog", "desc": "My travel vlog", "likes": 7, "dislikes": 1, "total_comments": 4, "owner": True}
                            ]
                        },
                        response_only=True,
                    )
                ]
            )
        }
    )
    def get(self, req):
        posts = Post.objects.filter(user=req.user).select_related('user__profile').prefetch_related('likes', 'comments')
        s = PostSerializer(posts, many=True, context={'request': req})
        return Response({'status': 'success', 'count': posts.count(), 'data': s.data})

class CommentCreateView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        tags=['Comments'],
        summary='Add a comment',
        description='Adds a comment to a specific post. Max 500 characters.',
        request={
            'application/json': {
                'type': 'object',
                'required': ['text'],
                'properties': {
                    'text': {'type': 'string', 'example': 'This place looks amazing! Can\'t wait to visit!', 'maxLength': 500}
                }
            }
        },
        responses={
            201: OpenApiResponse(
                description='Comment added',
                examples=[
                    OpenApiExample(
                        name='Success',
                        value={
                            "status": "success",
                            "message": "Comment added successfully",
                            "data": {
                                "id": 24, "post": 7, "text": "This place looks amazing!",
                                "owner": True,
                                "user": {"uid": 3, "fname": "Priya", "lname": "Singh", "pic": None},
                                "created": "2024-01-15T09:15:00Z", "updated": "2024-01-15T09:15:00Z"
                            }
                        },
                        response_only=True,
                    )
                ]
            ),
            400: OpenApiResponse(
                description='Validation error',
                examples=[
                    OpenApiExample(
                        name='Error — Empty Comment',
                        value={"text": ["Comment cannot be empty"]},
                        response_only=True,
                    ),
                    OpenApiExample(
                        name='Error — Too Long',
                        value={"text": ["Comment cannot exceed 500 characters"]},
                        response_only=True,
                    ),
                ]
            ),
            404: OpenApiResponse(
                description='Post not found',
                examples=[
                    OpenApiExample(
                        name='Error',
                        value={"detail": "No Post matches the given query."},
                        response_only=True,
                    )
                ]
            ),
        }
    )
    def post(self, req, pk):
        p = get_object_or_404(Post, pk=pk)
        s = CommentSerializer(data=req.data, context={'request': req})
        s.is_valid(raise_exception=True)
        s.save(user=req.user, post=p)
        return Response({'status': 'success', 'message': 'Comment added successfully', 'data': s.data},status=status.HTTP_201_CREATED)

class CommentUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Comments'],
        summary='Update a comment',
        description='Edits your own comment. Only `text` field is accepted.',
        request={
            'application/json': {
                'type': 'object',
                'required': ['text'],
                'properties': {
                    'text': {'type': 'string', 'example': 'Updated comment text', 'maxLength': 500}
                }
            }
        },
        responses={
            200: OpenApiResponse(
                description='Comment updated',
                examples=[
                    OpenApiExample(
                        name='Success',
                        value={
                            "status": "success",
                            "message": "Comment updated successfully",
                            "data": {
                                "id": 17, "post": 3, "text": "Updated comment text",
                                "owner": True,
                                "user": {"uid": 4, "fname": "Alex", "lname": "Doe", "pic": None},
                                "created": "2024-01-15T10:32:00Z", "updated": "2024-01-15T11:00:00Z"
                            }
                        },
                        response_only=True,
                    )
                ]
            ),
            403: OpenApiResponse(
                description='Not the comment owner',
                examples=[
                    OpenApiExample(
                        name='Error — Forbidden',
                        value={
                            "status": "error",
                            "message": "Permission denied",
                            "errors": {"permission": ["You can only edit your own comments"]}
                        },
                        response_only=True,
                    )
                ]
            ),
            404: OpenApiResponse(
                description='Comment not found',
                examples=[
                    OpenApiExample(
                        name='Error',
                        value={"detail": "No Comment matches the given query."},
                        response_only=True,
                    )
                ]
            ),
        }
    )
    def patch(self, req, pk):
        c = get_object_or_404(Comment, pk=pk)
        if c.user != req.user:
            return Response({'status': 'error', 'message': 'Permission denied', 'errors': {'permission': ['You can only edit your own comments']}},status=status.HTTP_403_FORBIDDEN)
        s = CommentSerializer(c, data=req.data, partial=True, context={'request': req})
        s.is_valid(raise_exception=True)
        s.save()
        return Response({'status': 'success', 'message': 'Comment updated successfully', 'data': s.data})

class CommentDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        tags=['Comments'],
        summary='Delete a comment',
        description='Permanently deletes your own comment.',
        responses={
            200: OpenApiResponse(
                description='Comment deleted',
                examples=[
                    OpenApiExample(
                        name='Success',
                        value={"status": "success", "message": "Comment deleted successfully"},
                        response_only=True,
                    )
                ]
            ),
            403: OpenApiResponse(
                description='Not the comment owner',
                examples=[
                    OpenApiExample(
                        name='Error — Forbidden',
                        value={
                            "status": "error",
                            "message": "Permission denied",
                            "errors": {"permission": ["You can only delete your own comments"]}
                        },
                        response_only=True,
                    )
                ]
            ),
            404: OpenApiResponse(
                description='Comment not found',
                examples=[
                    OpenApiExample(
                        name='Error',
                        value={"detail": "No Comment matches the given query."},
                        response_only=True,
                    )
                ]
            ),
        }
    )
    def delete(self, req, pk):
        c = get_object_or_404(Comment, pk=pk)
        if c.user != req.user:
            return Response({'status': 'error', 'message': 'Permission denied', 'errors': {'permission': ['You can only delete your own comments']}},status=status.HTTP_403_FORBIDDEN)
        c.delete()
        return Response({'status': 'success', 'message': 'Comment deleted successfully'}, status=status.HTTP_200_OK)

class PostLikeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Posts'],
        summary='Like or dislike a post',
        description=(
            "Toggle a like or dislike on a post.\n\n"
        ),
        request={
            'application/json': {
                'type': 'object',
                'required': ['like'],
                'properties': {
                    'like': {'type': 'boolean', 'example': True, 'description': 'true = like, false = dislike'}
                }
            }
        },
        responses={
            201: OpenApiResponse(
                description='Reaction created',
                examples=[
                    OpenApiExample(
                        name='Like Created',
                        value={
                            "status": "success", "message": "Post liked",
                            "data": {"action": "created", "like": True, "likes": 5, "dislikes": 2}
                        },
                        response_only=True,
                    )
                ]
            ),
            200: OpenApiResponse(
                description='Reaction updated or removed',
                examples=[
                    OpenApiExample(
                        name='Like Removed',
                        value={
                            "status": "success", "message": "Like removed",
                            "data": {"action": "removed", "like": True, "likes": 4, "dislikes": 2}
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name='Switched to Dislike',
                        value={
                            "status": "success", "message": "Changed to dislike",
                            "data": {"action": "updated", "like": False, "likes": 4, "dislikes": 3}
                        },
                        response_only=True,
                    ),
                ]
            ),
            400: OpenApiResponse(
                description='Invalid or missing like field',
                examples=[
                    OpenApiExample(
                        name='Error — Missing Field',
                        value={
                            "status": "error", "message": "Invalid request",
                            "errors": {"like": ["This field is required. Send true to like, false to dislike"]}
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name='Error — Wrong Type',
                        value={
                            "status": "error", "message": "Invalid request",
                            "errors": {"like": ["Must be a boolean (true or false), not a string or number"]}
                        },
                        response_only=True,
                    ),
                ]
            ),
            404: OpenApiResponse(
                description='Post not found',
                examples=[
                    OpenApiExample(
                        name='Error',
                        value={"detail": "No Post matches the given query."},
                        response_only=True,
                    )
                ]
            ),
        },
        examples=[
            OpenApiExample(name='Like', value={"like": True}, request_only=True),
            OpenApiExample(name='Dislike', value={"like": False}, request_only=True),
        ]
    )
    def post(self, req, pk):
        p = get_object_or_404(Post, pk=pk)
        like = req.data.get('like')
        if like is None:
            return Response({'status': 'error', 'message': 'Invalid request', 'errors': {'like': ['This field is required. Send true to like, false to dislike']}},status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(like, bool):
            return Response({'status': 'error', 'message': 'Invalid request', 'errors': {'like': ['Must be a boolean (true or false), not a string or number']}},status=status.HTTP_400_BAD_REQUEST)
        existing = PostLike.objects.filter(post=p, user=req.user).first()
        if existing:
            if existing.like == like:
                existing.delete()
                return Response({'status': 'success','message': f'{"Like" if like else "Dislike"} removed',
                    'data': {'action': 'removed', 'like': like, 'likes': p.likes.filter(like=True).count(), 'dislikes': p.likes.filter(like=False).count()}
                })
            else:
                existing.like = like
                existing.save()
                return Response({'status': 'success','message': f'Changed to {"like" if like else "dislike"}',
                    'data': {'action': 'updated', 'like': like, 'likes': p.likes.filter(like=True).count(), 'dislikes': p.likes.filter(like=False).count()}
                })
        else:
            PostLike.objects.create(post=p, user=req.user, like=like)
            return Response({'status': 'success','message': f'Post {"liked" if like else "disliked"}',
                'data': {'action': 'created', 'like': like, 'likes': p.likes.filter(like=True).count(), 'dislikes': p.likes.filter(like=False).count()}
            }, status=status.HTTP_201_CREATED)