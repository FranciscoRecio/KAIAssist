from fastapi import APIRouter, Request, Response, WebSocket
from fastapi.responses import HTMLResponse
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from src.services.audio_streaming_service import AudioStreamingService

router = APIRouter()

@router.post("/webhook")
async def handle_incoming_call(request: Request):
    """Handle incoming call and set up media stream"""
    response = VoiceResponse()
    response.say("Thank you for calling Kayako. Please wait while I connect you to an agent.")
    
    #print(f"URL hostname: {request.url.hostname}")
    #print(f"Header host: {request.headers.get('host')}")
    
    # Get the host from the request headers (this will be the ngrok URL)
    host = request.headers.get('host', '')
    # Ensure we use wss:// for WebSocket connections
    host = f"wss://{host}"
    
    # Set up the media stream with the full path
    websocket_url = f'{host}/api/twilio/media-stream'
    #print(f"WebSocket URL: {websocket_url}")
    
    connect = Connect()
    connect.stream(url=websocket_url)
    response.append(connect)
    
    return Response(content=str(response), media_type="application/xml")

@router.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between Twilio and OpenAI"""
    #print("Client connecting...")
    streaming_service = AudioStreamingService()
    await streaming_service.handle_call_stream(websocket)
    print("WebSocket connection closed") 