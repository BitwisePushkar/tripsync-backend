from django.urls import path
from account import views

app_name = "account"

urlpatterns = [
    path("register/", views.UserRegistrationView.as_view(), name="register"),
    path("verify-otp/", views.VerifyRegistrationOTPView.as_view(), name="verify-otp"),
    path("resend-otp/", views.ResendOTPView.as_view(), name="resend-otp"),
    path("login/", views.UserLoginView.as_view(), name="login"),
    path("logout/", views.UserLogoutView.as_view(), name="logout"),
    path("password/reset/request/", views.PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("password/reset/verify-otp/", views.PasswordResetVerifyOTPView.as_view(), name="password-reset-verify-otp"),
    path("password/reset/confirm/", views.PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("deactivate/", views.DeactivateAccountView.as_view(), name="deactivate"),
    path("delete/", views.DeleteAccountView.as_view(), name="delete"),
]