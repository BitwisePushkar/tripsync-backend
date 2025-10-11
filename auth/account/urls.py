from django.urls import path
from account.views import UserRegistrationView, UserLoginView, UserListView, UserProfileView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('users/', UserListView.as_view(), name='user-list'),  
    path('profile/', UserProfileView.as_view(), name='user-profile'),
]