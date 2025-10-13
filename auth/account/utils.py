from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_otp_email(email, otp, purpose="verification"):
    """
    Send OTP email to user with improved error handling
    """
    if purpose == "verification":
        subject = "Email Verification OTP - TripSync"
        message = f"""
Hello,

Welcome to TripSync - Your Travel Planning Companion!
Your OTP for email verification is: {otp}
This OTP is valid for 10 minutes. Please do not share this OTP with anyone.
If you did not request this, please ignore this email.

Best regards,
TripSync Team
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
TripSync Team
"""
   
    try:
        logger.info(f"Attempting to send OTP email to {email}")
        logger.debug(f"Email settings - HOST: {settings.EMAIL_HOST}, PORT: {settings.EMAIL_PORT}, USER: {settings.EMAIL_HOST_USER}")
        
        result = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        
        if result == 1:
            logger.info(f"✓ OTP email sent successfully to {email}")
            return True
        else:
            logger.error(f"✗ Failed to send OTP email to {email} - send_mail returned {result}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Exception while sending email to {email}: {str(e)}")
        logger.exception("Full traceback:")
        return False


def test_email_configuration():
    """
    Test email configuration - useful for debugging
    """
    try:
        from django.core.mail import send_mail
        
        send_mail(
            subject='TripSync Email Test',
            message='If you receive this, your email configuration is working correctly!',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.EMAIL_HOST_USER],  
            fail_silently=False,
        )
        return True, "Test email sent successfully"
    except Exception as e:
        return False, f"Email test failed: {str(e)}"