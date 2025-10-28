from django.urls import path
from .views import (ProfileDetailView,  VerifyOTPView,ResendOTPView,EmergencySOSView)

app_name = 'personal'

urlpatterns = [
    path('profile/', ProfileDetailView.as_view(), name='profile-detail'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('emergency/sos/', EmergencySOSView.as_view(), name='emergency-sos'),
]