import json
import base64
import websockets
import asyncio
import os
from fastapi import WebSocket
from dotenv import load_dotenv
from fastapi import WebSocketDisconnect

class AudioStreamingService:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.system_message = (
            "You are a helpful and professional AI assistant. Keep responses concise "
            "and clear, as this is a phone conversation."
        )

    async def handle_call_stream(self, websocket: WebSocket) -> None:
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

        # Add new state variables for transcripts
        current_user_message = ""
        current_assistant_message = ""

        async def send_mark():
            """Send a mark event to Twilio"""
            if stream_sid:
                mark_event = {
                    "event": "mark",
                    "streamSid": stream_sid,
                    "mark": {"name": "responsePart"}
                }
                await websocket.send_json(mark_event)
                mark_queue.append('responsePart')

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

        async with websockets.connect(
            'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17',
            extra_headers={
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as openai_ws:
            # Initialize session with OpenAI
            await self._initialize_openai_session(openai_ws)
            
            async def receive_from_twilio():
                """Handle incoming audio from Twilio"""
                nonlocal stream_sid, latest_media_timestamp, response_start_timestamp_twilio, last_assistant_item
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
                except WebSocketDisconnect:
                    print("Client disconnected.")
                    if openai_ws.open:
                        await openai_ws.close()
                except Exception as e:
                    print(f"Error receiving from Twilio: {e}")

            async def send_to_twilio():
                """Handle outgoing audio to Twilio"""
                nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio, current_assistant_message
                try:
                    async for message in openai_ws:
                        response = json.loads(message)
                        print(f"Received event type: {response.get('type')}")  # Basic event type log
                        
                        # Detailed debug log for specific events
                        important_events = [
                            'conversation.item.created',
                            'response.audio_transcript.done',
                            'response.content_part.done',
                            'response.output_item.done',
                            'response.done',
                            'conversation.item.input_audio_transcription.completed'
                        ]
                        # if response.get('type') in important_events:
                        #     print(f"Full response: {json.dumps(response, indent=2)}")  # Detailed debug log
                        
                        # Handle assistant transcription (complete transcript)
                        if response.get('type') == 'response.audio_transcript.done':
                            transcript = response.get('transcript', '')
                            print(f"Assistant: {transcript}")
                            current_assistant_message = transcript

                        # Handle user transcription (comes after completion)
                        if response.get('type') == 'conversation.item.input_audio_transcription.completed':
                            transcript = response.get('transcript', '')
                            print(f"\nUser: {transcript}")
                            current_user_message = transcript

                        # Handle audio response
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

                            await send_mark()

                        # Handle interruption when speech is detected
                        if response.get('type') == 'input_audio_buffer.speech_started':
                            print("Speech started detected.")
                            if last_assistant_item:
                                print(f"Interrupting response with id: {last_assistant_item}")
                                await handle_speech_started_event()

                except Exception as e:
                    print(f"Error sending to Twilio: {e}")

            # Handle bidirectional communication
            await asyncio.gather(
                receive_from_twilio(),
                send_to_twilio()
            )

    async def _initialize_openai_session(self, openai_ws):
        """Initialize the OpenAI session with our preferences"""
        session_config = {
            "type": "session.update",
            "session": {
                "turn_detection": {"type": "server_vad"},
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "voice": "alloy",
                "instructions": self.system_message,
                "modalities": ["text", "audio"],
                "temperature": 0.7,
                "input_audio_transcription": {
                    "model": "whisper-1"
                }
            }
        }
        print("Initializing OpenAI session with config:", json.dumps(session_config, indent=2))  # Debug log
        await openai_ws.send(json.dumps(session_config)) 