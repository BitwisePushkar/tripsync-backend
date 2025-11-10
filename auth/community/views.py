from rest_framework.views import APIView
from rest_framework import status, parsers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample,OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from .models import Post, Comment, PostLike
from .serializers import PostSerializer, PostDetailSerializer, CommentSerializer

class PostListView(APIView):
    permission_classes = [AllowAny]    
    @extend_schema(
    tags=["Posts"],
    summary="List all posts",
    description=("Retrieve a list of all posts. "),
    parameters=[
        OpenApiParameter(name="user",type=OpenApiTypes.INT,location=OpenApiParameter.QUERY,description="Filter by user ID",required=False),
        OpenApiParameter(name="search",type=OpenApiTypes.STR,location=OpenApiParameter.QUERY,description="Search posts by title",required=False),
    ],
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="List of posts retrieved successfully",
            examples=[
                OpenApiExample(
                    name="Success Response",
                    summary="Example successful response",
                    value={
                        "status": "success",
                        "count": 2,
                        "data": [
                            {
                                "id": 1,
                                "title": "Trip to Paris",
                                "desc": "A wonderful trip!",
                                "photo": "https://cdn.com/img1.jpg"
                            },
                            {
                                "id": 2,
                                "title": "Hiking in Manali",
                                "desc": "Snow adventure!",
                                "photo": "https://cdn.com/img2.jpg"
                            }
                        ]
                    }
                )
            ]
        ),
    },
    )
    def get(self, req):
        posts = Post.objects.select_related('user__profile').all()        
        uid = req.query_params.get('user')
        if uid:
            try:
                posts = posts.filter(user__id=int(uid))
            except (ValueError, TypeError):
                pass        
        q = req.query_params.get('search')
        if q:
            posts = posts.filter(title__icontains=q.strip())        
        s = PostSerializer(posts, many=True, context={'request': req})
        return Response({'status': 'success','count': posts.count(),'data': s.data})
    
class PostCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]    
    @extend_schema(
        tags=["Posts"],
        summary="Create a new post",
        description=("Allows an authenticated user to create a new post."),
        request=PostSerializer,
        responses={
            201: OpenApiResponse(
                description="Post created successfully",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Success Response",
                        summary="Example of a successful post creation",
                        value={
                            "status": "success",
                            "message": "Post created successfully",
                            "data": {
                                "id": 5,
                                "title": "Sunset at Bali",
                                "desc": "Beautiful beach view!",
                                "photo": "https://cdn.com/uploads/bali-sunset.jpg"
                            }
                        },
                    )
                ],
            ),
            400: OpenApiResponse(
                description="Validation error",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Validation Error",
                        summary="Invalid data example",
                        value={
                            "status": "error",
                            "message": "Invalid input data.",
                            "errors": {
                                "title": ["This field is required."],
                                "photo": ["Invalid image format."]
                            }
                        },
                    )
                ],
            ),
        },
        examples=[
            OpenApiExample(
                "Create Post Example",
                summary="Example request body",
                description="Example request to create a post",
                value={
                    "title": "Sunset at Bali",
                    "desc": "Beautiful beach view!",
                    "photo": None
                },
                request_only=True,
            ),
        ],
    )
    def post(self, req):
        s = PostSerializer(data=req.data, context={'request': req})
        s.is_valid(raise_exception=True)
        s.save(user=req.user)        
        return Response({'status': 'success','message': 'Post created successfully','data': s.data}, status=status.HTTP_201_CREATED)

class PostDetailView(APIView):
    permission_classes = [AllowAny]   
    @extend_schema(
        tags=['Posts'],
        summary='Retrieve a single post',
        description='Retrieve full details of a specific post using its ID, including user info and comments.',
        responses={
            200: OpenApiResponse(
                description="Post details retrieved successfully",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Success Example",
                        summary="Successfully retrieved post details",
                        value={
                            "status": "success",
                            "message": "Post retrieved successfully.",
                            "data": {
                                "id": 1,
                                "title": "Trip to Paris",
                                "desc": "Visited the Eiffel Tower during my trip to Paris.",
                                "user": {"id": 3, "name": "John Doe"},
                                "comments": [
                                    {"id": 10, "text": "Looks great!", "user": {"id": 5, "name": "Alex"}},
                                    {"id": 11, "text": "I want to go too!", "user": {"id": 6, "name": "Lara"}}
                                ]
                            }
                        }
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Post not found",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Not Found Example",
                        summary="Post not found example",
                        value={
                            "status": "error",
                            "message": "Post not found.",
                            "errors": {"post_id": ["No post exists with this ID."]}
                        }
                    )
                ]
            ),
        },
    )
    def get(self, req, pk):
        p = get_object_or_404(Post.objects.select_related('user__profile').prefetch_related('comments__user__profile'),pk=pk)
        s = PostDetailSerializer(p, context={'request': req})
        return Response({'status': 'success','data': s.data})

class PostUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]   
    @extend_schema(
        tags=['Posts'],
        summary='Update an existing post',
        description='Update your own post.',
        request=PostSerializer,
        responses={
            200: OpenApiResponse(
                description="Post updated successfully",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Success Example",
                        summary="Successfully updated post",
                        value={
                            "status": "success",
                            "message": "Post updated successfully.",
                            "data": {
                                "id": 5,
                                "title": "Updated Bali Post",
                                "desc": "New sunset photo added.",
                                "photo": "https://cdn.com/bali_updated.jpg"
                            }
                        }
                    )
                ]
            ),
            403: OpenApiResponse(
                description="User is not the owner of the post",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Forbidden Example",
                        summary="User tried to update another user's post",
                        value={
                            "status": "error",
                            "message": "Permission denied",
                            "errors": {"permission": ["You can only edit your own posts."]}
                        }
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Post not found",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Not Found Example",
                        summary="Invalid post ID",
                        value={
                            "status": "error",
                            "message": "Post not found.",
                            "errors": {"post_id": ["Invalid post ID."]}
                        }
                    )
                ]
            ),
        },
        examples=[
            OpenApiExample(
                name="Request Example",
                summary="Example request body",
                value={"title": "Updated Bali Post", "desc": "New sunset photo added."},
                request_only=True
            ),
        ]
    )
    def patch(self, req, pk):
        p = get_object_or_404(Post, pk=pk)        
        if p.user != req.user:
            return Response({'status': 'error','message': 'Permission denied','errors': {'permission': ['You can only edit your own posts']}}, status=status.HTTP_403_FORBIDDEN)        
        s = PostSerializer(p, data=req.data, partial=True, context={'request': req})
        s.is_valid(raise_exception=True)
        s.save()        
        return Response({'status': 'success','message': 'Post updated successfully','data': s.data})

class PostDeleteView(APIView):
    permission_classes = [IsAuthenticated]    
    @extend_schema(
        tags=['Posts'],
        summary='Delete a post',
        description='Delete your own post.',
        responses={
            200: OpenApiResponse(
                description="Post deleted successfully",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Success Example",
                        summary="Post deleted",
                        value={
                            "status": "success",
                            "message": "Post deleted successfully"
                        }
                    )
                ]
            ),
            403: OpenApiResponse(
                description="User is not the owner of the post",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Forbidden Example",
                        summary="User tried to delete another user's post",
                        value={
                            "status": "error",
                            "message": "Permission denied",
                            "errors": {"permission": ["You can only delete your own posts."]}
                        }
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Post not found",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Not Found Example",
                        summary="Invalid post ID",
                        value={
                            "status": "error",
                            "message": "Post not found.",
                            "errors": {"post_id": ["Invalid post ID."]}
                        }
                    )
                ]
            ),
        },
    )
    def delete(self, req, pk):
        p = get_object_or_404(Post, pk=pk)        
        if p.user != req.user:
            return Response({'status': 'error','message': 'Permission denied','errors': {'permission': ['You can only delete your own posts']}}, status=status.HTTP_403_FORBIDDEN)        
        p.delete()
        return Response({'status': 'success','message': 'Post deleted successfully'})

class PostSearchView(APIView):
    permission_classes = [AllowAny]    
    @extend_schema(
        tags=['Posts'],
        summary='Search posts by title',
        description='Search for posts whose titles contain the given query string (case-insensitive).',
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search query string (e.g., "beach")',
                required=True
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Successful search results",
                response=PostSerializer(many=True),
                examples=[
                    OpenApiExample(
                        name='Search Response Example',
                        summary='Successful search result',
                        description='Example response showing posts related to "mountain".',
                        value={
                            "status": "success",
                            "query": "mountain",
                            "count": 2,
                            "data": [
                                {
                                    "id": 4,
                                    "title": "Mountain Trekking",
                                    "desc": "Adventure in the Himalayas!",
                                    "photo": "https://cdn.com/img4.jpg"
                                },
                                {
                                    "id": 7,
                                    "title": "Snowy Mountains",
                                    "desc": "Winter escape",
                                    "photo": "https://cdn.com/img7.jpg"
                                }
                            ]
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Missing or invalid search query",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name='Missing Query Example',
                        summary='No query provided',
                        value={
                            "status": "error",
                            "message": "Search query is required",
                            "errors": {"query": ["Please provide a search query"]}
                        }
                    )
                ]
            ),
        },
        examples=[
            OpenApiExample(
                name='Search Request Example',
                summary='Example search request',
                description='Search for posts containing the word "mountain".',
                value={"q": "mountain"}
            )
        ]
    )
    def get(self, req):
        q = req.query_params.get('q', '').strip()        
        if not q:
            return Response({'status': 'error','message': 'Search query is required','errors': {'query': ['Please provide a search query']}}, status=status.HTTP_400_BAD_REQUEST)        
        posts = Post.objects.filter(title__icontains=q).select_related('user__profile')
        s = PostSerializer(posts, many=True, context={'request': req})        
        return Response({'status': 'success','query': q,'count': posts.count(),'data': s.data})

class MyPostsView(APIView):
    permission_classes = [IsAuthenticated]    
    @extend_schema(
        tags=['Posts'],
        summary='List posts created by current user',
        description='Retrieve all posts created by the authenticated user.',
        responses={
            200: OpenApiResponse(
                description="Posts retrieved successfully",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name='Success Example',
                        summary='My posts retrieved successfully',
                        value={
                            "status": "success",
                            "message": "Posts retrieved successfully.",
                            "count": 2,
                            "data": [
                                {"id": 10, "title": "Sunset in Bali", "desc": "Beautiful sunset!", "photo": "https://cdn.com/img10.jpg"},
                                {"id": 12, "title": "Paris Vlog", "desc": "My travel vlog in Paris", "photo": "https://cdn.com/img12.jpg"}
                            ]
                        }
                    )
                ]
            ),
        }
    )
    def get(self, req):
        posts = Post.objects.filter(user=req.user).select_related('user__profile')
        s = PostSerializer(posts, many=True, context={'request': req})        
        return Response({'status': 'success','count': posts.count(),'data': s.data})

class CommentCreateView(APIView):
    permission_classes = [IsAuthenticated]    
    @extend_schema(
        tags=['Posts'],
        summary='Add a comment to a post',
        description='Authenticated users can post a comment under a specific post.',
        request=CommentSerializer,
        responses={
            201: OpenApiResponse(
                description="Comment created successfully",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name='Success Example',
                        summary='Comment added',
                        value={
                            "status": "success",
                            "message": "Comment added successfully",
                            "data": {
                                "id": 24,
                                "post": 7,
                                "user": {"id": 3, "full_name": "Priya Singh"},
                                "content": "This place looks amazing! Can’t wait to visit 😍",
                                "created_at": "2025-11-05T09:15:00Z",
                                "updated_at": "2025-11-05T09:15:00Z"
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Invalid input data",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name='Invalid Request Example',
                        summary='Missing comment content',
                        value={
                            "status": "error",
                            "message": "Invalid data",
                            "errors": {"content": ["This field is required."]}
                        }
                    )
                ]
            ),
            401: OpenApiResponse(
                description="Unauthorized",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name='Unauthorized Example',
                        summary='User not authenticated',
                        value={
                            "status": "error",
                            "message": "Authentication credentials were not provided."
                        }
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Post not found",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name='Post Not Found Example',
                        summary='Invalid post ID',
                        value={
                            "status": "error",
                            "message": "Post not found.",
                            "errors": {"post_id": ["No post exists with this ID."]}
                        }
                    )
                ]
            ),
        },
        examples=[
            OpenApiExample(
                name='Request Example',
                summary='Example request body',
                value={"content": "This place looks amazing! Can’t wait to visit 😍"},
                request_only=True
            )
        ]
    )
    def post(self, req, pk):
        p = get_object_or_404(Post, pk=pk)        
        s = CommentSerializer(data=req.data, context={'request': req})
        s.is_valid(raise_exception=True)
        s.save(user=req.user, post=p)        
        return Response({'status': 'success','message': 'Comment added successfully','data': s.data}, status=status.HTTP_201_CREATED)

class CommentUpdateView(APIView):
    permission_classes = [IsAuthenticated]   
    @extend_schema(
        tags=['Posts'],
        summary='Update a comment',
        description='Edit your own comment.',
        request=CommentSerializer,
        responses={
            200: OpenApiResponse(
                description="Comment updated successfully",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name='Success Example',
                        summary='Comment updated',
                        value={
                            "status": "success",
                            "message": "Comment updated successfully",
                            "data": {
                                "id": 17,
                                "post": 3,
                                "user": {"id": 4, "full_name": "Alex Doe"},
                                "content": "Actually, this trip looks even better after watching the vlog!",
                                "created_at": "2025-11-05T10:32:00Z",
                                "updated_at": "2025-11-05T11:00:00Z"
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Invalid input",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name='Invalid Request Example',
                        summary='Missing comment content',
                        value={
                            "status": "error",
                            "message": "Invalid data",
                            "errors": {"content": ["This field is required."]}
                        }
                    )
                ]
            ),
            403: OpenApiResponse(
                description="Forbidden: not comment owner",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name='Forbidden Example',
                        summary='Editing another user’s comment',
                        value={
                            "status": "error",
                            "message": "Permission denied",
                            "errors": {"permission": ["You can only edit your own comments"]}
                        }
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Comment not found",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name='Not Found Example',
                        summary='Invalid comment ID',
                        value={
                            "status": "error",
                            "message": "Comment not found",
                            "errors": {"comment_id": ["No comment exists with this ID."]}
                        }
                    )
                ]
            ),
        },
        examples=[
            OpenApiExample(
                name='Request Example',
                summary='Example update request',
                value={
                    "content": "Actually, this trip looks even better after watching the vlog!"
                },
                request_only=True
            )
        ]
    )
    def patch(self, req, pk):
        c = get_object_or_404(Comment, pk=pk)        
        if c.user != req.user:
            return Response({'status': 'error','message': 'Permission denied','errors': {'permission': ['You can only edit your own comments']}}, status=status.HTTP_403_FORBIDDEN)        
        s = CommentSerializer(c, data=req.data, partial=True, context={'request': req})
        s.is_valid(raise_exception=True)
        s.save()        
        return Response({'status': 'success','message': 'Comment updated successfully','data': s.data})

class CommentDeleteView(APIView):
    permission_classes = [IsAuthenticated]   
    @extend_schema(
        tags=['Posts'],
        summary='Delete a comment',
        description='Delete your own comment from a post.',
        responses={
            200: OpenApiResponse(
                description="Comment deleted successfully",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name='Success Example',
                        summary='Comment deleted',
                        value={
                            "status": "success",
                            "message": "Comment deleted successfully"
                        }
                    )
                ]
            ),
            403: OpenApiResponse(
                description="Forbidden: not comment owner",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name='Forbidden Example',
                        summary='Trying to delete another user’s comment',
                        value={
                            "status": "error",
                            "message": "Permission denied",
                            "errors": {"permission": ["You can only delete your own comments"]}
                        }
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Comment not found",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name='Not Found Example',
                        summary='Invalid comment ID',
                        value={
                            "status": "error",
                            "message": "Comment not found",
                            "errors": {"comment_id": ["No comment exists with this ID."]}
                        }
                    )
                ]
            ),
        }
    )
    def delete(self, req, pk):
        c = get_object_or_404(Comment, pk=pk)        
        if c.user != req.user:
            return Response({'status': 'error','message': 'Permission denied','errors': {'permission': ['You can only delete your own comments']}}, status=status.HTTP_403_FORBIDDEN)       
        c.delete()
        return Response({'status': 'success','message': 'Comment deleted successfully'}, status=status.HTTP_200_OK)

class PostLikeView(APIView):
    permission_classes = [IsAuthenticated]   
    @extend_schema(
        tags=['Posts'],
        summary='Like or dislike a post',
        description='Authenticated users can like or dislike a post.',
        request={'application/json': {'type': 'object','properties': {'like': {'type': 'boolean'}},'example': {'like': True}}},
        responses={
            201: OpenApiResponse(
                description="Post liked/disliked successfully",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name='Like Created',
                        summary='Post liked',
                        value={
                            "status": "success",
                            "message": "Post liked",
                            "data": {
                                "action": "created",
                                "like": True,
                                "likes": 5,
                                "dislikes": 2
                            }
                        }
                    )
                ]
            ),
            200: OpenApiResponse(
                description="Existing like/dislike updated or removed",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name='Like Removed',
                        summary='User removed their like',
                        value={
                            "status": "success",
                            "message": "Like removed",
                            "data": {
                                "action": "removed",
                                "like": True,
                                "likes": 4,
                                "dislikes": 2
                            }
                        }
                    ),
                    OpenApiExample(
                        name='Changed to Dislike',
                        summary='User switched like to dislike',
                        value={
                            "status": "success",
                            "message": "Changed to dislike",
                            "data": {
                                "action": "updated",
                                "like": False,
                                "likes": 4,
                                "dislikes": 3
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Invalid request data",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name='Invalid Request',
                        summary='Missing like field',
                        value={
                            "status": "error",
                            "message": "Invalid request",
                            "errors": {
                                "like": ["This field is required. Use true for like, false for dislike"]
                            }
                        }
                    )
                ]
            ),
        },
        examples=[
            OpenApiExample(
                name='Request Example',
                summary='Example request body',
                value={"like": True},
                request_only=True
            )
        ]
    )
    def post(self, req, pk):
        p = get_object_or_404(Post, pk=pk)
        like = req.data.get('like')        
        if like is None:
            return Response({'status': 'error','message': 'Invalid request','errors': {'like': ['This field is required. Use true for like, false for dislike']}}, status=status.HTTP_400_BAD_REQUEST)       
        existing = PostLike.objects.filter(post=p, user=req.user).first()        
        if existing:
            if existing.like == like:
                existing.delete()
                return Response({'status': 'success','message': f'{"Like" if like else "Dislike"} removed','data': {'action': 'removed','like': like,'likes': p.likes.filter(like=True).count(),'dislikes': p.likes.filter(like=False).count()}})
            else:
                existing.like = like
                existing.save()
                return Response({'status': 'success','message': f'Changed to {"like" if like else "dislike"}','data': {'action': 'updated','like': like,'likes': p.likes.filter(like=True).count(),'dislikes': p.likes.filter(like=False).count()}})
        else:
            PostLike.objects.create(post=p, user=req.user, like=like)
            return Response({'status': 'success','message': f'Post {"liked" if like else "disliked"}','data': {'action': 'created','like': like,'likes': p.likes.filter(like=True).count(),'dislikes': p.likes.filter(like=False).count()}}, status=status.HTTP_201_CREATED)