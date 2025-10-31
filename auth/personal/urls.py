from django.urls import path
from .views import (ProfileDetailView,  VerifyOTPView,ResendOTPView,EmergencySOSView,UserListView,UserProfileByNameView)

app_name = 'personal'

urlpatterns = [
    path('profile/', ProfileDetailView.as_view(), name='profile-detail'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('emergency/sos/', EmergencySOSView.as_view(), name='emergency-sos'),
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/search/', UserProfileByNameView.as_view(), name='user-profile-by-name'),
]