from rest_framework.views import APIView
from rest_framework import status, parsers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from .models import Post, Comment, PostLike
from .serializers import PostSerializer, PostDetailSerializer, CommentSerializer

class PostListView(APIView):
    permission_classes = [AllowAny]    
    @extend_schema(
        tags=['Posts'],
        summary='List posts',
        parameters=[
            OpenApiParameter('user', OpenApiTypes.INT, OpenApiParameter.QUERY,description='Filter by user ID', required=False),
            OpenApiParameter('search', OpenApiTypes.STR, OpenApiParameter.QUERY,description='Search by title', required=False)
        ],
        responses=PostSerializer(many=True)
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
        tags=['Posts'],
        summary='Create a new post',
        request=PostSerializer,
        responses={201: PostSerializer}
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
        summary='Get a specific post',
        responses={200: PostDetailSerializer}
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
        summary='Update a post',
        request=PostSerializer,
        responses={200: PostSerializer}
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
        responses={200: dict}
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
        parameters=[OpenApiParameter('q', OpenApiTypes.STR, OpenApiParameter.QUERY, description='Search query', required=True)],responses={200: PostSerializer(many=True)}
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
        summary='Get current user posts',
        responses={200: PostSerializer(many=True)}
    )
    def get(self, req):
        posts = Post.objects.filter(user=req.user).select_related('user__profile')
        s = PostSerializer(posts, many=True, context={'request': req})        
        return Response({'status': 'success','count': posts.count(),'data': s.data})

class CommentCreateView(APIView):
    permission_classes = [IsAuthenticated]    
    @extend_schema(
        tags=['Comments'],
        summary='Add a comment to a post',
        request=CommentSerializer,
        responses={201: CommentSerializer}
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
        tags=['Comments'],
        summary='Update a comment',
        request=CommentSerializer,
        responses={200: CommentSerializer}
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
        tags=['Comments'],
        summary='Delete a comment',
        responses={200: dict}
    )
    def delete(self, req, pk):
        c = get_object_or_404(Comment, pk=pk)        
        if c.user != req.user:
            return Response({'status': 'error','message': 'Permission denied','errors': {'permission': ['You can only delete your own comments']}}, status=status.HTTP_403_FORBIDDEN)       
        c.delete()
        return Response({'status': 'success','message': 'Comment deleted successfully'})

class PostLikeView(APIView):
    permission_classes = [IsAuthenticated]   
    @extend_schema(
        tags=['Likes'],
        summary='Like or dislike a post',
        request={'application/json': {'type': 'object', 'properties': {'like': {'type': 'boolean'}}}},
        responses={200: dict}
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