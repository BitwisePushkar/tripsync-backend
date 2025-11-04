from django.urls import path
from community import views

app_name = "community"

urlpatterns = [
    path("posts/", views.PostFeedView.as_view(), name="post-feed"),
    path("posts/my/", views.MyPostsView.as_view(), name="my-posts"),
    path("posts/create/", views.PostCreateView.as_view(), name="post-create"),
    path("posts/<int:pk>/", views.PostDetailView.as_view(), name="post-detail"),
    path("posts/<int:pk>/update/", views.PostUpdateView.as_view(), name="post-update"),
    path("posts/<int:pk>/delete/", views.PostDeleteView.as_view(), name="post-delete"),
    path("posts/<int:pk>/react/", views.PostReactView.as_view(), name="post-react"),
    path("share/post/<uuid:share_token>/",views.PostShareResolveView.as_view(),name="post-share-resolve",),
    path("posts/<int:pk>/comments/",views.CommentListView.as_view(),name="comment-list"),
    path("posts/<int:pk>/comments/add/", views.CommentCreateView.as_view(), name="comment-create"),
    path("comments/<int:pk>/delete/", views.CommentDeleteView.as_view(), name="comment-delete"),
    path("comments/<int:pk>/react/",views.CommentReactView.as_view(),name="comment-react"),
    path("posts/<int:pk>/view/",views.PostViewRecordView.as_view(),name="post-view"),
    path("users/<int:user_id>/follow/",views.FollowToggleView.as_view(),name="user-follow"),
    path("users/<int:user_id>/followers/",views.FollowerListView.as_view(),name="user-followers"),
    path("users/<int:user_id>/following/",views.FollowingListView.as_view(),name="user-following"),
    path("users/<int:user_id>/stats/",views.UserProfileStatsView.as_view(),name="user-stats"),
]