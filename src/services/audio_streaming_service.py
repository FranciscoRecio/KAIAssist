import json
import base64
import websockets
import asyncio
import os
from fastapi import WebSocket
from dotenv import load_dotenv
from fastapi import WebSocketDisconnect
from .conversation_service import ConversationService
from .search_service import KnowledgeBaseSearchService
from .ticket_service import KayakoTicketService
from .auth_service import KayakoAuthService
from .tool_service import ToolService
from ..models.tool import Tools

class AudioStreamingService:
    SYSTEM_MESSAGE = """You are a helpful and professional AI assistant for phone conversations. 

        CRITICAL CONVERSATION RULES - YOU MUST FOLLOW THESE EXACTLY:

        1. INITIAL RESPONSE:
           - ALWAYS use search_knowledge_base tool first
           - Provide answer using ONLY the tool's response
           - IMMEDIATELY follow your answer with "Did that answer your question?"
           - Wait for caller's response

        2. AFTER CALLER RESPONDS TO "Did that answer your question?":
           IF CALLER SAYS NO:
           - Say "I apologize, but I don't have enough information to fully answer your question. I'll have a representative call you back to assist with this. Thank you for calling."
           - Use end_call tool with reason "insufficient_information"
           - End conversation

           IF CALLER SAYS YES:
           - IMMEDIATELY ask "Do you have any other questions I can help you with?"
           - Wait for caller's response

        3. AFTER CALLER RESPONDS TO "Do you have any other questions?":
           IF CALLER SAYS NO:
           - Say "Thank you for calling. Have a great day!"
           - Use end_call tool with reason "question_answered"
           - End conversation

           IF CALLER SAYS YES:
           - Start over from step 1 with their new question

        IMPORTANT:
        - Never skip asking "Did that answer your question?"
        - Never skip asking "Do you have any other questions?"
        - Never provide information without using search_knowledge_base tool
        - Never continue conversation after using end_call tool
        - Keep all responses concise and clear."""

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.system_message = self.SYSTEM_MESSAGE
        self.conversation_service = ConversationService()
        self.tool_service = ToolService()
        self.caller_number = None

    async def handle_call_stream(self, websocket: WebSocket, caller_number: str = None) -> None:
        """Handle WebSocket connections between Twilio and OpenAI"""
        self.caller_number = caller_number
        await websocket.accept()
        print("Client connected")

        # Connection specific state
        stream_sid = None
        latest_media_timestamp = 0
        last_assistant_item = None
        mark_queue = []
        response_start_timestamp_twilio = None

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
            #print("Handling speech started event.")
            if mark_queue and response_start_timestamp_twilio is not None:
                elapsed_time = latest_media_timestamp - response_start_timestamp_twilio

                if last_assistant_item:
                    #print(f"Truncating item with ID: {last_assistant_item}, Truncated at: {elapsed_time}ms")
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
                            #print(f"Incoming stream has started {stream_sid}")
                            response_start_timestamp_twilio = None
                            latest_media_timestamp = 0
                            last_assistant_item = None
                            # Start new conversation
                            self.conversation_service.start_conversation(stream_sid)
                        elif data['event'] == 'stop':
                            print("Call ended.")
                            if stream_sid:
                                # Get the conversation and create ticket
                                conversation = self.conversation_service.get_conversation(stream_sid)
                                if conversation and self.caller_number:
                                    ticket_service = KayakoTicketService(KayakoAuthService())
                                    ticket_service.make_ticket(conversation, self.caller_number)
                                self.conversation_service.save_conversation(stream_sid)
                            if openai_ws.open:
                                await openai_ws.close()
                            break
                        elif data['event'] == 'mark':
                            if mark_queue:
                                mark_queue.pop(0)
                except WebSocketDisconnect:
                    print("Client disconnected.")
                    if stream_sid:
                        self.conversation_service.save_conversation(stream_sid)
                    if openai_ws.open:
                        await openai_ws.close()
                except Exception as e:
                    print(f"Error receiving from Twilio: {e}")

            async def send_to_twilio():
                """Handle outgoing audio to Twilio"""
                nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio
                try:
                    async for message in openai_ws:
                        response = json.loads(message)
                        #print(f"Received event type: {response.get('type')}")
                        if response.get('type') == 'error':
                            print(f"Error details: {json.dumps(response, indent=2)}")
                        
                        # Handle assistant transcription
                        if response.get('type') == 'response.audio_transcript.done':
                            transcript = response.get('transcript', '')
                            print(f"Assistant: {transcript}")
                            self.conversation_service.add_message(stream_sid, "assistant", transcript)

                        # Handle caller transcription
                        if response.get('type') == 'conversation.item.input_audio_transcription.completed':
                            transcript = response.get('transcript', '')
                            print(f"\nCaller: {transcript}")
                            self.conversation_service.add_message(stream_sid, "caller", transcript)

                        # Handle audio response
                        if response.get('type') == 'response.audio.delta' and 'delta' in response:
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
                            #print("Speech started detected.")
                            if last_assistant_item:
                                #print(f"Interrupting response with id: {last_assistant_item}")
                                await handle_speech_started_event()

                        # Handle function calls
                        if response.get('type') == 'response.function_call_arguments.done':
                            await self.tool_service.handle_function_call(
                                function_name=response.get('name'),
                                function_args=response.get('arguments', '{}'),
                                call_id=response.get('call_id'),
                                websocket=websocket,
                                openai_ws=openai_ws,
                                stream_sid=stream_sid,
                                conversation_service=self.conversation_service,
                                caller_number=self.caller_number
                            )

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
                },
                "tools": Tools.get_all_tools()
            }
        }
        await openai_ws.send(json.dumps(session_config))

        # Send initial greeting
        await self._send_initial_conversation_item(openai_ws)

    async def _send_initial_conversation_item(self, openai_ws):
        """Send initial conversation item if AI talks first."""
        initial_conversation_item = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Greet the user with 'Hi! This is Kai speaking. How can I assist you?'"
                    }
                ]
            }
        }

        
        await openai_ws.send(json.dumps(initial_conversation_item))
        await openai_ws.send(json.dumps({"type": "response.create"})) 