from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    path('login/', views.UserLoginView.as_view(), name='login'),
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),
    path('users/', views.UserListView.as_view(), name='user-list'),
    path('email/send-otp/', views.SendEmailOTPView.as_view(), name='send-email-otp'),
    path('email/verify-otp/', views.VerifyEmailOTPView.as_view(), name='verify-email-otp'),
    path('password/reset/request/', views.PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password/reset/verify/', views.PasswordResetVerifyOTPView.as_view(), name='password-reset-verify'),
    path('password/reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
]
