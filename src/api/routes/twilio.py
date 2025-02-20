from fastapi import APIRouter, Request
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
    response.say("Welcome to KAI Assist. How can I help you today?")
    
    return {"twiml": str(response)}

@router.post("/gather")
async def handle_gather(request: Request):
    """Handle gathered user input from keypad or speech"""
    form_data = await request.form()
    
    # Process gathered input
    response = VoiceResponse()
    response.say("Thank you for your input. Please wait while I process your request.")
    
    return {"twiml": str(response)} 