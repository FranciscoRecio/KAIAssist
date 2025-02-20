from twilio.rest import Client
from src.config.settings import Settings

class TwilioService:
    def __init__(self):
        settings = Settings()
        self.client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )
        self.phone_number = settings.TWILIO_PHONE_NUMBER
    
    async def make_call(self, to_number: str, callback_url: str):
        """Make an outbound call"""
        try:
            call = self.client.calls.create(
                to=to_number,
                from_=self.phone_number,
                url=callback_url
            )
            return call.sid
        except Exception as e:
            # Log the error
            raise Exception(f"Failed to make call: {str(e)}")
    
    async def send_message(self, to_number: str, message: str):
        """Send an SMS message"""
        try:
            message = self.client.messages.create(
                to=to_number,
                from_=self.phone_number,
                body=message
            )
            return message.sid
        except Exception as e:
            # Log the error
            raise Exception(f"Failed to send message: {str(e)}") 