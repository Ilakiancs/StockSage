import os
from twilio.rest import Client
from twilio.base.exceptions import TwilioException
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)

TARGET_PHONE_NUMBER = os.getenv("TARGET_PHONE_NUMBER")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

def send_sms(body: str) -> bool:
    """
    Send SMS message using Twilio
    
    Args:
        body: Message content to send
        
    Returns:
        bool: True if message sent successfully, False otherwise
    """
    try:
        if not body:
            logger.error("Cannot send SMS: empty message body")
            return False
            
        if not all([TARGET_PHONE_NUMBER, TWILIO_PHONE_NUMBER, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN]):
            logger.error("Cannot send SMS: missing Twilio configuration")
            return False
            
        if len(body) > 1600:  # Twilio limit
            logger.warning(f"Message too long ({len(body)} chars), truncating")
            body = body[:1597] + "..."
            
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            to=TARGET_PHONE_NUMBER,
            from_=TWILIO_PHONE_NUMBER,
            body=body
        )
        
        logger.info(f"SMS sent successfully: {message.sid}")
        return True
        
    except TwilioException as e:
        logger.error(f"Twilio error sending SMS: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending SMS: {e}")
        return False
