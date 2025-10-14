from django.core.mail import send_mail
from django.conf import settings

def send_otp_email(email, otp, purpose="verification"):
    if purpose == "verification":
        subject = "Email Verification OTP - TripSync"
        message = f"""
Hello,

Welcome to TripSync - Your Travel Planning Companion!
Your OTP for email verification is: {otp}
This OTP is valid for 10 minutes. Please do not share this OTP with anyone.
If you did not request this, please ignore this email.
Best regards,
TripSync
"""
    else:
        subject = "Password Reset OTP - TripSync"
        message = f"""
Hello,

You have requested to reset your password for your TripSync account.
Your OTP for password reset is: {otp}
This OTP is valid for 10 minutes. Please do not share this OTP with anyone.
If you did not request this, please secure your account immediately.
Best regards,
TripSync

"""
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False