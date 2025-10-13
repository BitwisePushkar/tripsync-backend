from django.urls import path
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from . import views

def test_email(request):
    try:
        send_mail(
            'Test Email',
            'This is a test email from TripSync',
            settings.DEFAULT_FROM_EMAIL,
            ['arnav2412020@akgec.ac.in'],
            fail_silently=False,
        )
        return JsonResponse({'status': 'success', 'message': 'Email sent'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
    
urlpatterns = [
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    path('login/', views.UserLoginView.as_view(), name='login'),
    path('logout/', views.UserLogoutView.as_view(), name='logout'), 
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),
    path('users/', views.UserListView.as_view(), name='user-list'),
    path('email/send-otp/', views.SendEmailOTPView.as_view(), name='send-email-otp'),
    path('test-email/', test_email),
    path('email/verify-otp/', views.VerifyEmailOTPView.as_view(), name='verify-email-otp'),
    path('password/reset/request/', views.PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password/reset/verify/', views.PasswordResetVerifyOTPView.as_view(), name='password-reset-verify'),
    path('password/reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
]

