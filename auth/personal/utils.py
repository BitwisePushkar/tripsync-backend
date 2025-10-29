from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging

logger = logging.getLogger(__name__)

class SMSService:
    def __init__(self):
        self.account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        self.auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        self.from_number = getattr(settings, 'TWILIO_PHONE_NUMBER', None)
        if not all([self.account_sid, self.auth_token, self.from_number]):
            logger.error("Twilio credentials not configured properly")
            raise ValueError("Twilio credentials missing in settings")
        self.client = Client(self.account_sid, self.auth_token)
    
    def send_otp(self, phone_number, otp_code):
        try:
            otp_expiry = getattr(settings, 'OTP_EXPIRY_MINUTES', 5)
            message_body = (
                f"Your verification code is: {otp_code}\n\n"
                f"This code will expire in {otp_expiry} minutes.\n\n"
                f"Do not share this code with anyone."
            )
            message = self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=phone_number
            )   
            logger.info(f"OTP SMS sent successfully to {phone_number}. SID: {message.sid}")
            return True, f"OTP sent successfully to {phone_number}"
        
        except TwilioRestException as e:
            logger.error(f"Twilio error: {str(e)}")
            return False, f"Failed to send SMS: {str(e)}"
        
        except Exception as e:
            logger.error(f"Unexpected error sending OTP SMS: {str(e)}")
            return False, "Failed to send SMS. Please try again later."
    
    def send_verification_success(self, phone_number, name):
        try:
            message_body = (
                f"Hi {name}! Your phone number has been verified successfully. "
                f"Welcome aboard!"
            )
            message = self.client.messages.create(body=message_body,from_=self.from_number,to=phone_number)
            
            logger.info(f"Verification success SMS sent to {phone_number}. SID: {message.sid}")
            return True, "Confirmation sent"
        
        except Exception as e:
            logger.error(f"Error sending confirmation SMS: {str(e)}")
            return False, str(e)
        
    def send_emergency_alert(self, emergency_number, user_name, user_phone, custom_message='', location=''):
        try:
            message_body = f"🚨 EMERGENCY ALERT 🚨\n\n"
            message_body += f"{user_name} has triggered an emergency SOS!\n\n"
            if custom_message:
                message_body += f"Message: {custom_message}\n\n"
            else:
                message_body += "They need immediate assistance!\n\n"
            if location:
                message_body += f"Location: {location}\n\n"
            message_body += f"Contact them immediately at: {user_phone}\n\n"
            message_body += "Please check on them as soon as possible."
            message = self.client.messages.create(body=message_body,from_=self.from_number,to=emergency_number)
            
            logger.info(
                f"Emergency alert sent successfully to {emergency_number} "
                f"for user {user_name}. SID: {message.sid}"
            )
            return True, f"Emergency alert sent to {emergency_number}"
        
        except TwilioRestException as e:
            logger.error(f"Twilio error sending emergency alert: {str(e)}")
            return False, f"Failed to send emergency alert: {str(e)}"
        
        except Exception as e:
            logger.error(f"Unexpected error sending emergency alert: {str(e)}")
            return False, "Failed to send emergency alert. Please try again later."