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
from .langchain_agent_service import LangChainAgentService
from ..models.tool import Tools

class AudioStreamingService:
    SYSTEM_MESSAGE = """You are a helpful and professional AI assistant for phone conversations.

        CRITICAL INSTRUCTIONS - YOU MUST FOLLOW THESE EXACTLY:

        1. For EVERY user input, you MUST use the get_agent_response function
           - NEVER respond to the user without first calling get_agent_response
           - Pass the user's exact input as the query parameter
           - Wait for the function to return a response
           - Use ONLY the function's response to answer the user

        IMPORTANT:
        - You MUST use get_agent_response for EVERY user input
        - This includes questions, statements, and any other user utterances
        - NEVER skip using get_agent_response
        - NEVER provide information from your own knowledge
        - Keep all responses concise and clear."""

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.system_message = self.SYSTEM_MESSAGE
        self.conversation_service = ConversationService()
        self.knowledge_service = KnowledgeBaseSearchService()
        self.tool_service = ToolService()
        self.agent_service = LangChainAgentService()
        
        # Initialize auth and ticket services
        self.auth_service = KayakoAuthService()
        self.ticket_service = KayakoTicketService(self.auth_service)
        
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
            await self._initialize_openai_session(openai_ws)
            
            # Initialize the agent service for this call
            await self.agent_service.initialize_for_call(
                websocket=websocket,
                openai_ws=openai_ws,
                stream_sid=stream_sid,
                conversation_service=self.conversation_service,
                knowledge_service=self.knowledge_service
            )
            
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
                                    # Debug the conversation structure
                                    print(f"Conversation type: {type(conversation)}")
                                    print(f"Conversation keys: {conversation.keys() if hasattr(conversation, 'keys') else 'No keys'}")
                                    
                                    # Extract messages from the conversation structure
                                    if isinstance(conversation, dict) and 'messages' in conversation:
                                        messages = conversation['messages']
                                    else:
                                        messages = conversation  # Assume it's already the messages list
                                    
                                    # Create a ticket using the ticket service
                                    ticket_result = self.ticket_service.make_ticket(
                                        messages, 
                                        self.caller_number  # This can be None
                                    )
                                    print(f"Ticket creation result: {ticket_result}")
                                
                                # Save the conversation
                                self.conversation_service.save_conversation(stream_sid)
                            
                            if openai_ws.open:
                                await openai_ws.close()
                            break
                        elif data['event'] == 'mark':
                            if mark_queue:
                                mark_queue.pop(0)
                        elif data['event'] == 'transcript':
                            transcript = data.get('transcript', {})
                            text = transcript.get('text', '')
                            
                            if text and text.strip():  # Only process non-empty text
                                print(f"User said: {text}")
                                
                                # Add to conversation history
                                if stream_sid:
                                    self.conversation_service.add_message(stream_sid, 'caller', text)
                                
                                # Process through LangChain agent
                                agent_response = await self.agent_service.process_user_input({"query": text})
                                
                                if agent_response.get("success", False):
                                    print(f"Agent processed input successfully")
                                    # The response is handled by the agent's tools, which will send instructions
                                    # through the OpenAI WebSocket when needed
                                else:
                                    print(f"Agent processing failed: {agent_response.get('error', 'Unknown error')}")
                                    # Send a fallback response if agent processing fails
                                    fallback_message = {
                                        "type": "response.create",
                                        "response": {
                                            "instructions": "I'm sorry, I'm having trouble processing that. Could you please repeat?"
                                        }
                                    }
                                    await openai_ws.send(json.dumps(fallback_message))
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
                nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio, current_state
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
                            
                            # Update state based on the message content
                            message_text = transcript.lower()
                            
                            if "did that answer your question" in message_text:
                                current_state = "awaiting_answer_feedback"
                                self.conversation_service.update_call_state(stream_sid, current_state)
                            elif "do you have any other questions" in message_text:
                                current_state = "awaiting_more_questions"
                                self.conversation_service.update_call_state(stream_sid, current_state)

                        # Handle caller transcription
                        if response.get('type') == 'conversation.item.input_audio_transcription.completed':
                            transcript = response.get('transcript', '')
                            print(f"\nCaller: {transcript}")
                            self.conversation_service.add_message(stream_sid, "caller", transcript)
                            
                            # We don't need to process the transcript here
                            # OpenAI will make a function call to get_agent_response
                            # which will be handled in the function call section

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
                                # Add interruption handling through tool service
                                if stream_sid and last_assistant_item:
                                    elapsed_time = latest_media_timestamp - response_start_timestamp_twilio if response_start_timestamp_twilio else 0
                                    await self.tool_service.handle_interruption(
                                        websocket, 
                                        openai_ws, 
                                        stream_sid,
                                        last_assistant_item,
                                        elapsed_time
                                    )

                        # Handle function calls
                        if response.get('type') == 'response.function_call_arguments.done':
                            function_name = response.get('name')
                            function_args = response.get('arguments', '{}')
                            call_id = response.get('call_id')
                            
                            print(f"Function call detected: {function_name}")
                            print(f"Function arguments: {function_args}")
                            print(f"Call ID: {call_id}")
                            
                            # Process all function calls through our agent
                            await self.tool_service.get_agent_response(
                                function_name=function_name,
                                function_args=function_args,
                                call_id=call_id,
                                openai_ws=openai_ws,
                                stream_sid=stream_sid,
                                conversation_service=self.conversation_service,
                                agent_service=self.agent_service
                            )
                            
                            print(f"Function call {function_name} processed")

                except Exception as e:
                    print(f"Error sending to Twilio: {e}")
                    import traceback
                    print(traceback.format_exc())

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
                "turn_detection": {
                    "type": "server_vad",
                    "create_response": False  # Disable automatic responses
                },
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

        # Send initial greeting directly
        greeting_message = "Hello! Thank you for calling. How can I help you today?"
        instruction_message = {
            "type": "response.create",
            "response": {
                "instructions": f"Say exactly: '{greeting_message}'"
            }
        }
        await openai_ws.send(json.dumps(instruction_message))
        print("Initial greeting sent directly")

        # After sending the initial greeting, test the function call
        test_function_call = {
            "type": "response.create",
            "response": {
                "instructions": "Call the get_agent_response function with the query 'test query'"
            }
        }
        await openai_ws.send(json.dumps(test_function_call))
        print("Test function call sent") 