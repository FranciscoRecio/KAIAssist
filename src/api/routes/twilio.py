from fastapi import APIRouter, Request, Response
from twilio.twiml.voice_response import VoiceResponse
from src.services.twilio_service import TwilioService
from src.agents.call_handler import CallHandlerAgent

router = APIRouter()
twilio_service = TwilioService()
call_handler = CallHandlerAgent()

@router.post("/webhook")
async def handle_incoming_call(request: Request):
    """Handle incoming Twilio voice calls"""
    form_data = await request.form()
    
    # Create TwiML response
    response = VoiceResponse()
    gather = response.gather(
        input='speech',
        action='/api/twilio/gather',
        method='POST',
        language='en-US',
        timeout=3
    )
    gather.say("Welcome to KAI Assist. How can I help you today?")
    
    # If no input received, retry
    response.redirect('/api/twilio/webhook')
    
    return Response(content=str(response), media_type="application/xml")

@router.post("/gather")
async def handle_gather(request: Request):
    """Handle gathered user input from speech"""
    form_data = await request.form()
    user_speech = form_data.get('SpeechResult', '')
    
    # Create TwiML response
    response = VoiceResponse()
    response.say(f"I heard you say: {user_speech}. Let me process that.")
    
    return Response(content=str(response), media_type="application/xml") 