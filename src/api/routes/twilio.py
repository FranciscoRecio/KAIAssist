from fastapi import APIRouter, Request, Response, WebSocket
from fastapi.responses import HTMLResponse
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from src.services.audio_streaming_service import AudioStreamingService
from urllib.parse import quote

router = APIRouter()

@router.post("/webhook")
async def handle_incoming_call(request: Request):
    """Handle incoming call and set up media stream"""
    # Extract the caller's phone number
    form_data = await request.form()
    caller_number = form_data.get('From', 'Unknown')
    
    response = VoiceResponse()
    response.say("Thank you for calling Kayako. Please wait while I connect you to an agent.")
    
    # Get the host from the request headers
    host = request.headers.get('host', '')
    host = f"wss://{host}"
    
    connect = Connect()
    # Add caller number to customParameters
    connect.stream(
        url=f'{host}/api/twilio/media-stream',
        custom_parameters={'caller_number': caller_number}
    )
    response.append(connect)
    
    return Response(content=str(response), media_type="application/xml")

@router.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between Twilio and OpenAI"""
    streaming_service = AudioStreamingService()
    await streaming_service.handle_call_stream(websocket) 