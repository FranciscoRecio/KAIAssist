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
        response_in_progress = False
        audio_playing = False
        audio_chunks_received = 0  # Track number of audio chunks received

        # Initialize state before stream_sid is available
        current_state = "initial"
        self.conversation_service.update_call_state(stream_sid, current_state)

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
            await self._initialize_openai_session(openai_ws, websocket, stream_sid)
            
            async def receive_from_twilio():
                """Handle incoming audio from Twilio"""
                nonlocal stream_sid, latest_media_timestamp, response_start_timestamp_twilio, last_assistant_item, current_state
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
                            #print(f"\nCall started - Stream ID: {stream_sid}")
                            response_start_timestamp_twilio = None
                            latest_media_timestamp = 0
                            last_assistant_item = None
                            # Start new conversation and set initial state
                            self.conversation_service.start_conversation(stream_sid)
                            self.conversation_service.update_call_state(stream_sid, current_state)
                        elif data['event'] == 'stop':
                            print("Call ended.")
                            if stream_sid:
                                # Get the conversation and create ticket
                                conversation = self.conversation_service.get_conversation(stream_sid)
                                if conversation:
                                    # Process the conversation regardless of caller_number
                                    print(f"\nProcessing conversation data. Caller number: {self.caller_number or 'Unknown'}")
                                    # Mock ticket service for now - we'll handle the None caller_number case
                                    if self.caller_number:
                                        print(f"Caller identified: {self.caller_number}")
                                    else:
                                        print("Caller number not available")
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
                nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio, current_state, response_in_progress, audio_playing, audio_chunks_received
                try:
                    async for message in openai_ws:
                        response = json.loads(message)
                        
                        # Debug logging for all event types
                        print(f"OpenAI event: {response.get('type')}")
                        
                        if response.get('type') == 'error':
                            print(f"Error details: {json.dumps(response, indent=2)}")
                        
                        # Handle audio chunks
                        if response.get('type') == 'response.audio.delta' and 'delta' in response:
                            try:
                                audio_playing = True
                                audio_chunks_received += 1
                                
                                # Decode and re-encode the audio payload
                                audio_payload = base64.b64encode(base64.b64decode(response['delta'])).decode('utf-8')
                                
                                # Debug log for audio chunks
                                print(f"Sending audio chunk #{audio_chunks_received} to Twilio")
                                
                                # Send the audio to Twilio
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
                            except Exception as e:
                                print(f"Error sending audio to Twilio: {e}")
                                import traceback
                                print(traceback.format_exc())
                        
                        # Handle audio end
                        if response.get('type') == 'response.audio.done':
                            print(f"Audio response complete. Sent {audio_chunks_received} chunks.")
                            audio_playing = False
                            audio_chunks_received = 0
                        
                        # Handle assistant transcription
                        if response.get('type') == 'response.audio_transcript.done':
                            transcript = response.get('transcript', '')
                            print(f"Assistant: {transcript}")
                            self.conversation_service.add_message(stream_sid, "assistant", transcript)
                            response_in_progress = False  # Response is complete
                            audio_playing = False  # Audio is no longer playing
                            
                            # Check if we need to update the state based on the message content
                            message_text = transcript.lower()
                            
                            if "did that answer your question" in message_text:
                                current_state = "awaiting_answer_feedback"
                                self.conversation_service.update_call_state(stream_sid, current_state)
                            elif "do you have any other questions" in message_text:
                                current_state = "awaiting_more_questions"
                                self.conversation_service.update_call_state(stream_sid, current_state)

                        # Handle response start
                        if response.get('type') == 'response.create.started':
                            response_in_progress = True  # Response has started
                        
                        # Handle caller transcription
                        if response.get('type') == 'conversation.item.input_audio_transcription.completed':
                            transcript = response.get('transcript', '')
                            print(f"\nCaller: {transcript}")
                            self.conversation_service.add_message(stream_sid, "caller", transcript)
                            
                            # After processing a user message, enforce the conversation flow
                            # Only if no response is currently in progress
                            if not response_in_progress:
                                await self.tool_service.enforce_conversation_flow(
                                    current_state,
                                    self.conversation_service,
                                    stream_sid,
                                    openai_ws,
                                    websocket
                                )

                        # Handle interruption when speech is detected - ONLY if audio is actually playing
                        if response.get('type') == 'input_audio_buffer.speech_started':
                            print("Speech started detected.")
                            if audio_playing and last_assistant_item:
                                print(f"Interrupting response with id: {last_assistant_item}")
                                await handle_speech_started_event()
                            else:
                                print("Speech detected but no audio is playing - not treating as interruption")

                        # Handle function calls
                        if response.get('type') == 'response.function_call_arguments.done':
                            function_name = response.get('name')
                            function_args = response.get('arguments', '{}')
                            call_id = response.get('call_id')
                            
                            # Set response_in_progress to False before handling function call
                            response_in_progress = False
                            
                            await self.tool_service.handle_function_call(
                                function_name=function_name,
                                function_args=function_args,
                                call_id=call_id,
                                websocket=websocket,
                                openai_ws=openai_ws,
                                stream_sid=stream_sid,
                                conversation_service=self.conversation_service,
                                caller_number=self.caller_number
                            )
                            
                            # Update the state based on the function call
                            if function_name == "search_knowledge_base":
                                current_state = "initial_response"
                                self.conversation_service.update_call_state(stream_sid, current_state)
                                # Set response_in_progress to True after handling search_knowledge_base
                                response_in_progress = True
                            elif function_name == "end_call":
                                current_state = "ending"
                                self.conversation_service.update_call_state(stream_sid, current_state)
                            
                            # After the function call completes, enforce the conversation flow
                            # Only if no response is currently in progress
                            if not response_in_progress:
                                await self.tool_service.enforce_conversation_flow(
                                    current_state,
                                    self.conversation_service,
                                    stream_sid,
                                    openai_ws,
                                    websocket
                                )

                except Exception as e:
                    print(f"Error sending to Twilio: {e}")
                    import traceback
                    print(traceback.format_exc())

            # Handle bidirectional communication
            await asyncio.gather(
                receive_from_twilio(),
                send_to_twilio()
            )

    async def _initialize_openai_session(self, openai_ws, websocket=None, stream_sid=None):
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
        
        print('Sending session update')
        await openai_ws.send(json.dumps(session_config))

        # Wait a moment for the session to initialize
        await asyncio.sleep(2)
        
        print("Session initialized with audio output enabled")
        
        # Send initial greeting immediately after session initialization
        await self._send_initial_conversation_item(openai_ws)
        
        # Update the state if we have a stream_sid
        if stream_sid:
            self.conversation_service.update_call_state(stream_sid, "initial")

    async def _send_initial_conversation_item(self, openai_ws):
        """Send initial conversation item if AI talks first."""
        print("Sending initial conversation item")
        
        # Use a direct instruction instead of a conversation item
        initial_instruction = {
            "type": "response.create",
            "response": {
                "instructions": "Greet the user with 'Hi! This is Kai speaking. How can I assist you today?' Wait for the user to respond."
            }
        }
        
        await openai_ws.send(json.dumps(initial_instruction))
        print("Initial greeting instruction sent") 