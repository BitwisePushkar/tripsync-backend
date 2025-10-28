from rest_framework import viewsets, status, parsers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from .models import Post
from .serializers import PostSerializer


class IsEmailVerified(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if not request.user.is_email_verified:
            return False
        return True


@extend_schema_view(
    list=extend_schema(
        tags=['Posts'],
        summary='List all posts',
        description='Retrieve a list of all posts.',
        parameters=[
            OpenApiParameter(
                name='user',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filter posts by user ID',
                required=False)]),
    create=extend_schema(
        tags=['Posts'],
        summary='Create a new post',
        description='Create a new post with optional image and video uploads.',),
    retrieve=extend_schema(
        tags=['Posts'], 
        summary='Get a specific post',
        description='Retrieve details of a specific post by ID. Public endpoint.'),
    update=extend_schema(
        tags=['Posts'],
        summary='Update a post',
        description='Update an existing post.',),
    partial_update=extend_schema(
        tags=['Posts'],
        summary='Partially update a post',
        description='Partially update an existing post.',),
    destroy=extend_schema(
        tags=['Posts'],
        summary='Delete a post',
        description='Delete a post.',))

class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.select_related('user').all()
    serializer_class = PostSerializer
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        elif self.action in ['create', 'update', 'partial_update', 'destroy', 'my_posts']:
            permission_classes = [IsEmailVerified]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = Post.objects.all()
        user_id = self.request.query_params.get('user', None)
        if user_id:
            queryset = queryset.filter(user__id=user_id)
        return queryset
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        if not request.user.is_email_verified:
            return Response({
                'status': 'error',
                'message': 'Email verification required',
                'errors': {'account': ['Please verify your email before creating posts']}
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        
        return Response({
            'status': 'success',
            'message': 'Post created successfully',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        if instance.user != request.user:
            return Response({
                'status': 'error',
                'message': 'Permission denied',
                'errors': {'permission': ['You can only edit your own post']}
            }, status=status.HTTP_403_FORBIDDEN)
        
        if not request.user.is_email_verified:
            return Response({
                'status': 'error',
                'message': 'Email verification required',
                'errors': {'account': ['Your email must be verified to update posts']}
            }, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            'status': 'success',
            'message': 'Post updated',
            'data': serializer.data})
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.user != request.user:
            return Response({
                'status': 'error',
                'message': 'Permission denied',
                'errors': {'permission': ['You Can only delete posts made by you']}
            }, status=status.HTTP_403_FORBIDDEN)

        if not request.user.is_email_verified:
            return Response({
                'status': 'error',
                'message': 'Email verification required',
                'errors': {'account': ['Your email must be verified to delete posts']}
            }, status=status.HTTP_403_FORBIDDEN)
        
        self.perform_destroy(instance)
        return Response({
            'status': 'success',
            'message': 'Post deleted successfully'
        }, status=status.HTTP_200_OK)
    
    @extend_schema(
        tags=['Posts'],
        summary='Get current user posts',
        description='Retrieve all posts created by the authenticated user.',
    )
    @action(detail=False, methods=['get'], permission_classes=[IsEmailVerified])
    def my_posts(self, request):
        posts = Post.objects.filter(user=request.user)
        serializer = self.get_serializer(posts, many=True)
        return Response({
            'status': 'success',
            'count': posts.count(),
            'data': serializer.data
        })
    
    @extend_schema(
        tags=['Posts'],
        summary='Check verification status',
        description='Check if the current user can create/edit posts (must be email verified).',)
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def verify_status(self, request):
        user = request.user
        
        return Response({
            'status': 'success',
            'data': {
                'is_authenticated': True,
                'is_email_verified': user.is_email_verified,
                'can_create_posts': user.is_email_verified,
                'user_id': user.id,
                'email': user.email
            }
        })