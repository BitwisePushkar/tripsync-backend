from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_otp_email(email, otp, purpose="verification"):
    try:
        sendgrid_api_key = getattr(settings, 'SENDGRID_API_KEY', None)
        if not sendgrid_api_key:
            logger.error("SENDGRID_API_KEY not configured in settings")
            return False
        
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@tripsync.com')
        
        if purpose == "verification":
            subject = "Email Verification OTP - TripSync"
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #4F46E5; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                    .content {{ background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; }}
                    .otp-box {{ background-color: #fff; border: 2px dashed #4F46E5; padding: 20px; text-align: center; margin: 20px 0; border-radius: 5px; }}
                    .otp-code {{ font-size: 32px; font-weight: bold; color: #4F46E5; letter-spacing: 5px; }}
                    .footer {{ background-color: #f3f4f6; padding: 15px; text-align: center; font-size: 12px; color: #6b7280; border-radius: 0 0 5px 5px; }}
                    .warning {{ color: #dc2626; font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Welcome to TripSync!</h1>
                    </div>
                    <div class="content">
                        <h2>Email Verification</h2>
                        <p>Hello,</p>
                        <p>Thank you for registering with TripSync - Your Travel Planning Companion!</p>
                        <p>To verify your email address, please use the following OTP code:</p>
                        
                        <div class="otp-box">
                            <div class="otp-code">{otp}</div>
                        </div>
                        
                        <p><strong>This OTP is valid for 10 minutes.</strong></p>
                        <p class="warning">⚠️ Please do not share this OTP with anyone.</p>
                        <p>If you did not request this verification, please ignore this email.</p>
                    </div>
                    <div class="footer">
                        <p>© 2024 TripSync. All rights reserved.</p>
                        <p>This is an automated email, please do not reply.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            plain_content = f"""
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
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #dc2626; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                    .content {{ background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; }}
                    .otp-box {{ background-color: #fff; border: 2px dashed #dc2626; padding: 20px; text-align: center; margin: 20px 0; border-radius: 5px; }}
                    .otp-code {{ font-size: 32px; font-weight: bold; color: #dc2626; letter-spacing: 5px; }}
                    .footer {{ background-color: #f3f4f6; padding: 15px; text-align: center; font-size: 12px; color: #6b7280; border-radius: 0 0 5px 5px; }}
                    .warning {{ color: #dc2626; font-weight: bold; }}
                    .security-notice {{ background-color: #fef2f2; border-left: 4px solid #dc2626; padding: 10px; margin: 15px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Password Reset Request</h1>
                    </div>
                    <div class="content">
                        <h2>Reset Your Password</h2>
                        <p>Hello,</p>
                        <p>You have requested to reset your password for your TripSync account.</p>
                        <p>Your OTP for password reset is:</p>
                        
                        <div class="otp-box">
                            <div class="otp-code">{otp}</div>
                        </div>
                        
                        <p><strong>This OTP is valid for 10 minutes.</strong></p>
                        
                        <div class="security-notice">
                            <p class="warning">🔒 Security Notice</p>
                            <p>If you did not request this password reset, please secure your account immediately and contact our support team.</p>
                        </div>
                        
                        <p class="warning">⚠️ Never share this OTP with anyone, including TripSync staff.</p>
                    </div>
                    <div class="footer">
                        <p>© 2024 TripSync. All rights reserved.</p>
                        <p>This is an automated email, please do not reply.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            plain_content = f"""
Hello,

You have requested to reset your password for your TripSync account.

Your OTP for password reset is: {otp}

This OTP is valid for 10 minutes. Please do not share this OTP with anyone.

If you did not request this, please secure your account immediately and contact support.

Best regards,
TripSync Team
            """
        
        message = Mail(
            from_email=Email(from_email),
            to_emails=To(email),
            subject=subject,
            plain_text_content=Content("text/plain", plain_content),
            html_content=Content("text/html", html_content)
        )
        
        sg = SendGridAPIClient(sendgrid_api_key)
        response = sg.send(message)
        
        if response.status_code in [200, 201, 202]:
            logger.info(f"OTP email sent successfully to {email} via SendGrid")
            return True
        else:
            logger.error(f"SendGrid returned status code {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending email via SendGrid: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False