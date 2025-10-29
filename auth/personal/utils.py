from django.conf import settings
import requests
import logging

logger = logging.getLogger(__name__)

class SMSService:
    def __init__(self):
        self.api_key = getattr(settings, 'TWOFACTOR_API_KEY', None)
        self.base_url = "https://2factor.in/API/V1"
        
        if not self.api_key:
            logger.error("2Factor API key not configured properly")
            raise ValueError("2Factor API key missing in settings")
    
    def send_otp(self, phone_number, otp_code):
        try:
            phone_number = phone_number.replace('+', '').replace(' ', '').replace('-', '')
            if phone_number.startswith('91') and len(phone_number) == 12:
                phone_number = phone_number[2:]
            url = f"{self.base_url}/{self.api_key}/SMS/{phone_number}/{otp_code}/AUTOGEN"           
            response = requests.get(url, timeout=10)
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get('Status') == 'Success':
                session_id = response_data.get('Details', '')
                logger.info(f"OTP SMS sent successfully to {phone_number}. Session ID: {session_id}")
                return True, f"OTP sent successfully to {phone_number}"
            else:
                error_msg = response_data.get('Details', 'Unknown error')
                logger.error(f"2Factor API error: {error_msg}")
                return False, f"Failed to send SMS: {error_msg}"
        
        except requests.exceptions.Timeout:
            logger.error("2Factor API request timeout")
            return False, "SMS service timeout. Please try again."
        
        except requests.exceptions.RequestException as e:
            logger.error(f"2Factor API request error: {str(e)}")
            return False, "Failed to send SMS. Please check your connection."
        
        except Exception as e:
            logger.error(f"Unexpected error sending OTP SMS: {str(e)}")
            return False, "Failed to send SMS. Please try again later."
    
    def send_custom_sms(self, phone_number, message):
        try:
            phone_number = phone_number.replace('+', '').replace(' ', '').replace('-', '')
            if phone_number.startswith('91') and len(phone_number) == 12:
                phone_number = phone_number[2:]
            url = f"{self.base_url}/{self.api_key}/ADDON_SERVICES/SEND/TSMS"           
            payload = {
                'From': 'TWOFAC',
                'To': phone_number,
                'Msg': message
            }            
            response = requests.post(url, data=payload, timeout=10)
            response_data = response.json()            
            if response.status_code == 200 and response_data.get('Status') == 'Success':
                logger.info(f"Custom SMS sent successfully to {phone_number}")
                return True, f"SMS sent successfully to {phone_number}"
            else:
                error_msg = response_data.get('Details', 'Unknown error')
                logger.warning(f"2Factor TSMS not available: {error_msg}")
                return False, f"SMS service not available: {error_msg}"
        
        except Exception as e:
            logger.warning(f"Custom SMS failed: {str(e)}")
            return False, "Custom SMS not available"
    
    def send_verification_success(self, phone_number, name):
        try:
            message = f"Hi {name}! Your phone number has been verified successfully. Welcome aboard!"
            success, msg = self.send_custom_sms(phone_number, message)
            if not success:
                logger.info(f"Verification success SMS skipped (TSMS not available)")
            return True, "Verification completed"
        
        except Exception as e:
            logger.info(f"Verification success SMS skipped: {str(e)}")
            return True, "Verification completed"
    
    def send_emergency_alert(self, emergency_number, user_name, user_phone, custom_message='', location=''):
        try:
            message_body = f"EMERGENCY ALERT\n\n"
            message_body += f"{user_name} has triggered an emergency SOS!\n\n"         
            if custom_message:
                message_body += f"Message: {custom_message}\n\n"
            else:
                message_body += "They need immediate assistance!\n\n"
            
            if location:
                message_body += f"Location: {location}\n\n"
            
            message_body += f"Contact them immediately at: {user_phone}\n\n"
            message_body += "Please check on them as soon as possible."
            success, msg = self.send_custom_sms(emergency_number, message_body)
            
            if success:
                logger.info(f"Emergency alert sent successfully to {emergency_number} for user {user_name}")
                return True, f"Emergency alert sent to {emergency_number}"
            else:
                emergency_code = "112112"
                logger.warning(f"TSMS failed, trying emergency code via AUTOGEN")
                clean_number = emergency_number.replace('+', '').replace(' ', '').replace('-', '')
                if clean_number.startswith('91') and len(clean_number) == 12:
                    clean_number = clean_number[2:]            
                url = f"{self.base_url}/{self.api_key}/SMS/{clean_number}/{emergency_code}/AUTOGEN"
                response = requests.get(url, timeout=10)
                response_data = response.json()               
                if response.status_code == 200 and response_data.get('Status') == 'Success':
                    logger.info(f"Emergency code sent to {emergency_number}")
                    return True, f"Emergency notification sent to {emergency_number}"
                else:
                    return False, "Emergency SMS service not available"
        
        except Exception as e:
            logger.error(f"Unexpected error sending emergency alert: {str(e)}")
            return False, "Failed to send emergency alert. Please try again later."