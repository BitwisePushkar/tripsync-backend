from django.urls import path
from .views import (PersonalDetailsCreateView,VerifyOTPView,ResendOTPView,ProfileDetailView)

app_name = 'personal'

urlpatterns = [
    path('create/', PersonalDetailsCreateView.as_view(), name='profile-create'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('', ProfileDetailView.as_view(), name='profile-detail'),
]
