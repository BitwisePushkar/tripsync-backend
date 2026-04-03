from django.conf import settings
from django.core.mail import send_mail
import logging

logger = logging.getLogger(__name__)

def send_otp_email(email, otp, purpose="verification"):
    try:
        if purpose == "verification":
            subject = "Email Verification OTP - TripSync"
            html_content = f"""
            <html>
            <body>
                <h2>Welcome to TripSync!</h2>
                <p>Your email verification OTP is:</p>
                <h1 style="color: #4CAF50; font-size: 32px; letter-spacing: 5px;">{otp}</h1>
                <p>This OTP is valid for 10 minutes.</p>
                <p><small>If you didn't request this, please ignore this email.</small></p>
                <br>
                <p>Best regards,<br>TripSync Team</p>
            </body>
            </html>
            """
        else:
            subject = "Password Reset OTP - TripSync"
            html_content = f"""
            <html>
            <body>
                <h2>Password Reset Request</h2>
                <p>Your password reset OTP is:</p>
                <h1 style="color: #FF5722; font-size: 32px; letter-spacing: 5px;">{otp}</h1>
                <p>This OTP is valid for 10 minutes.</p>
                <p><small>If you didn't request this, please secure your account immediately.</small></p>
                <br>
                <p>Best regards,<br>TripSync Team</p>
            </body>
            </html>
            """
        send_mail(
            subject=subject,
            message='',                                  
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_content,
            fail_silently=False,                      
        )
        logger.info(f"OTP email sent successfully to {email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send OTP email to {email}: {str(e)}")
        logger.exception("Full traceback:")
        return False