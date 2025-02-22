from fastapi import APIRouter, Request, Response, WebSocket
from fastapi.responses import HTMLResponse
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
import json
import base64
import websockets
import asyncio
import os
from dotenv import load_dotenv

router = APIRouter()
load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
SYSTEM_MESSAGE = (
    "You are a helpful and professional AI assistant. Keep responses concise "
    "and clear, as this is a phone conversation."
)

@router.post("/webhook")
async def handle_incoming_call(request: Request):
    """Handle incoming call and set up media stream"""
    response = VoiceResponse()
    response.say("Please wait while I connect you to the AI assistant.")
    response.pause(length=1)
    response.say("OK, you can start talking!")
    
    print(f"URL hostname: {request.url.hostname}")
    print(f"Header host: {request.headers.get('host')}")
    
    # Get the host from the request headers (this will be the ngrok URL)
    host = request.headers.get('host', '')
    # Ensure we use wss:// for WebSocket connections
    host = f"wss://{host}"
    
    # Set up the media stream with the full path
    websocket_url = f'{host}/api/twilio/media-stream'
    print(f"WebSocket URL: {websocket_url}")
    
    connect = Connect()
    connect.stream(url=websocket_url)
    response.append(connect)
    
    return Response(content=str(response), media_type="application/xml")

@router.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between Twilio and OpenAI"""
    print("Client connecting...")
    await websocket.accept()
    print("Client connected")

    # Connection specific state
    stream_sid = None
    latest_media_timestamp = 0
    last_assistant_item = None
    mark_queue = []
    response_start_timestamp_twilio = None

    async with websockets.connect(
        'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17',
        extra_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }
    ) as openai_ws:
        # Initialize session with OpenAI
        await initialize_openai_session(openai_ws)
        
        async def receive_from_twilio():
            """Handle incoming audio from Twilio"""
            nonlocal stream_sid, latest_media_timestamp
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    if data['event'] == 'media' and openai_ws.open:
                        latest_media_timestamp = int(data['media']['timestamp'])
                        audio_data = {
                            "type": "input_audio_buffer.append",
                            "audio": data['media']['payload']
                        }
                        await openai_ws.send(json.dumps(audio_data))
                    elif data['event'] == 'start':
                        stream_sid = data['start']['streamSid']
                        print(f"Incoming stream has started {stream_sid}")
                        response_start_timestamp_twilio = None
                        latest_media_timestamp = 0
                        last_assistant_item = None
                    elif data['event'] == 'mark':
                        if mark_queue:
                            mark_queue.pop(0)
            except Exception as e:
                print(f"Error receiving from Twilio: {e}")

        async def send_to_twilio():
            """Handle outgoing audio to Twilio"""
            nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio
            try:
                async for message in openai_ws:
                    response = json.loads(message)
                    
                    if response.get('type') == 'response.audio.delta' and 'delta' in response:
                        # Properly handle base64 encoding for audio payload
                        audio_payload = base64.b64encode(base64.b64decode(response['delta'])).decode('utf-8')
                        await websocket.send_json({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {
                                "payload": audio_payload
                            }
                        })

                        if response_start_timestamp_twilio is None:
                            response_start_timestamp_twilio = latest_media_timestamp

                        if response.get('item_id'):
                            last_assistant_item = response['item_id']

                        await send_mark(websocket, stream_sid)

                    # Handle interruption when speech is detected
                    if response.get('type') == 'input_audio_buffer.speech_started':
                        print("Speech started detected.")
                        if last_assistant_item:
                            print(f"Interrupting response with id: {last_assistant_item}")
                            await handle_speech_started_event()

            except Exception as e:
                print(f"Error sending to Twilio: {e}")

        async def handle_speech_started_event():
            """Handle interruption when the caller's speech starts."""
            nonlocal response_start_timestamp_twilio, last_assistant_item
            print("Handling speech started event.")
            if mark_queue and response_start_timestamp_twilio is not None:
                elapsed_time = latest_media_timestamp - response_start_timestamp_twilio

                if last_assistant_item:
                    print(f"Truncating item with ID: {last_assistant_item}, Truncated at: {elapsed_time}ms")
                    truncate_event = {
                        "type": "conversation.item.truncate",
                        "item_id": last_assistant_item,
                        "content_index": 0,
                        "audio_end_ms": elapsed_time
                    }
                    await openai_ws.send(json.dumps(truncate_event))

                await websocket.send_json({
                    "event": "clear",
                    "streamSid": stream_sid
                })

                mark_queue.clear()
                last_assistant_item = None
                response_start_timestamp_twilio = None

        async def send_mark(connection, stream_sid):
            if stream_sid:
                mark_event = {
                    "event": "mark",
                    "streamSid": stream_sid,
                    "mark": {"name": "responsePart"}
                }
                await connection.send_json(mark_event)
                mark_queue.append('responsePart')

        # Handle bidirectional communication
        await asyncio.gather(
            receive_from_twilio(),
            send_to_twilio()
        )

async def initialize_openai_session(openai_ws):
    """Initialize the OpenAI session with our preferences"""
    session_config = {
        "type": "session.update",
        "session": {
            "turn_detection": {"type": "server_vad"},
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": "alloy",
            "instructions": SYSTEM_MESSAGE,
            "modalities": ["text", "audio"],
            "temperature": 0.7,
        }
    }
    await openai_ws.send(json.dumps(session_config)) 