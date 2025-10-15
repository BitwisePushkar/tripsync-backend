from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_otp_email(email, otp, purpose="verification"):
    """
    Send OTP email using SendGrid HTTP API (works on Render Free tier)
    """
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
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
        
        message = Mail(
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=email,
            subject=subject,
            html_content=html_content
        )
        
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        
        if response.status_code in [200, 201, 202]:
            logger.info(f"✓ OTP email sent successfully to {email} via SendGrid API")
            return True
        else:
            logger.error(f"✗ SendGrid API returned status {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"✗ SendGrid API error for {email}: {str(e)}")
        logger.exception("Full traceback:")
        return False