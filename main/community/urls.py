from django.urls import path
from .views import (PostListView, PostCreateView, PostDetailView,PostUpdateView, PostDeleteView, MyPostsView,
                    CommentCreateView, CommentUpdateView, CommentDeleteView,PostLikeView,)

app_name = 'community'

urlpatterns = [
    path('posts/',PostListView.as_view(),name='post-list'),
    path('posts/create/',PostCreateView.as_view(),name='post-create'),
    path('posts/my/',MyPostsView.as_view(),name='my-posts'),
    path('posts/detail/<int:pk>/',PostDetailView.as_view(),name='post-detail'),
    path('posts/<int:pk>/update/',PostUpdateView.as_view(),name='post-update'),
    path('posts/<int:pk>/delete/',PostDeleteView.as_view(),name='post-delete'),
    path('posts/<int:pk>/like/',PostLikeView.as_view(),name='post-like'),
    path('posts/<int:pk>/comments/',CommentCreateView.as_view(),name='comment-create'),
    path('comments/<int:pk>/update/',CommentUpdateView.as_view(),name='comment-update'),
    path('comments/<int:pk>/delete/',CommentDeleteView.as_view(),name='comment-delete'),
]