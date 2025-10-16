from django.urls import path
from . import views
    
urlpatterns = [
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    path('verify-otp/', views.VerifyRegistrationOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', views.ResendRegistrationOTPView.as_view(), name='resend-otp'),
    path('login/', views.UserLoginView.as_view(), name='login'),
    path('logout/', views.UserLogoutView.as_view(), name='logout'), 
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),
    path('users/', views.UserListView.as_view(), name='user-list'),
    path('password/reset/request/', views.PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password/reset/verify/', views.PasswordResetVerifyView.as_view(), name='password-reset-verify'),
]