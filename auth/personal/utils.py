from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging

logger = logging.getLogger(__name__)

class TwilioSMSService:
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
            message = self.client.messages.create(body=message_body,from_=self.from_number,to=phone_number)
            logger.info(f"SMS sent successfully to {phone_number}. SID: {message.sid}")
            return True, f"OTP sent successfully to {phone_number}"
        
        except TwilioRestException as e:
            logger.error(f"Twilio error: {str(e)}")
            return False, f"Failed to send SMS: {str(e)}"
        
        except Exception as e:
            logger.error(f"Unexpected error sending SMS: {str(e)}")
            return False, "Failed to send SMS. Please try again later."
    
    def send_verification_success(self, phone_number, name):
        try:
            message_body = f"Hi {name}! Your phone number has been verified successfully. Welcome aboard!"
            message = self.client.messages.create(body=message_body,from_=self.from_number,to=phone_number)
            logger.info(f"Verification success SMS sent to {phone_number}")
            return True, "Confirmation sent"
        
        except Exception as e:
            logger.error(f"Error sending confirmation SMS: {str(e)}")
            return False, str(e)