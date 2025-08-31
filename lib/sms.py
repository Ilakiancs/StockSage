import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

TARGET_PHONE_NUMBER = os.getenv("TARGET_PHONE_NUMBER")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

def send_sms(body: str) -> None:
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    client.messages.create(
        to=TARGET_PHONE_NUMBER,
        from_=TWILIO_PHONE_NUMBER,
        body=body
    )
