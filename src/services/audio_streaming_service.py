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

class AudioStreamingService:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.system_message = """You are a helpful and professional AI assistant. 

        IMPORTANT:
        - ALWAYS use the search_knowledge_base tool for EVERY question
        - Only use information from the tool's response to answer questions
        - Keep responses concise and clear, as this is a phone conversation
        - If the tool's response doesn't contain enough information to answer fully, say "I apologize, but I don't have enough information to fully answer your question. I'll have a representative call you back to assist with this."
        - Do not make assumptions or add information beyond what's in the tool's response
        - Never answer without first using the search_knowledge_base tool

        Your primary role is to search our knowledge base using the search_knowledge_base tool and provide answers based solely on the information it returns.

        CRITICAL: You MUST use the search_knowledge_base tool BEFORE providing ANY response to the user. Do not engage in conversation or provide any information without first searching the knowledge base."""
        self.conversation_service = ConversationService()
        self.knowledge_base_service = KnowledgeBaseSearchService()

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
                            # Start new conversation
                            self.conversation_service.start_conversation(stream_sid)
                        elif data['event'] == 'stop':
                            print("Call ended.")
                            if stream_sid:
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
                        print(f"Received event type: {response.get('type')}")
                        if response.get('type') == 'error':
                            print(f"Error details: {json.dumps(response, indent=2)}")
                        
                        # Handle tool calls
                        if response.get('type') == 'tool_calls':
                            print("\nReceived tool call from OpenAI")
                            for tool_call in response.get('tool_calls', []):
                                print(f"Tool called: {tool_call.get('function', {}).get('name')}")
                                if tool_call.get('function', {}).get('name') == 'search_knowledge_base':
                                    try:
                                        args = json.loads(tool_call['function']['arguments'])
                                        print(f"Tool arguments: {args}")
                                        
                                        kb_response = self.knowledge_base_service.get_kb_answer(args['query'])
                                        print("Got knowledge base response")
                                        
                                        # Send tool response back to OpenAI
                                        tool_response = {
                                            "type": "tool_output",
                                            "id": tool_call['id'],
                                            "output": kb_response
                                        }
                                        print(f"Sending tool response back to OpenAI: {tool_call['id']}")
                                        await openai_ws.send(json.dumps(tool_response))
                                    except Exception as e:
                                        print(f"Error in tool call handling: {e}")
                                        import traceback
                                        print(traceback.format_exc())
                        
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
                            print("Speech started detected.")
                            if last_assistant_item:
                                print(f"Interrupting response with id: {last_assistant_item}")
                                await handle_speech_started_event()

                        # Handle function calls
                        if response.get('type') == 'response.function_call_arguments.delta':
                            print("\nReceived function call delta from OpenAI")
                            print(f"Delta content: {response}")
                        
                        if response.get('type') == 'response.function_call_arguments.done':
                            print("\nFunction call arguments complete")
                            try:
                                # Get the complete function call
                                function_name = response.get('name')
                                function_args = response.get('arguments', '{}')
                                call_id = response.get('call_id')
                                print(f"Function called: {function_name}")
                                print(f"Arguments: {function_args}")
                                
                                if function_name == 'search_knowledge_base':
                                    args = json.loads(function_args)
                                    kb_response = self.knowledge_base_service.get_kb_answer(args['query'])

                                    tool_response = {
                                        "type": "response.create",
                                        "response": {
                                            "instructions": kb_response
                                        }
                                    }

                                    print("Sending knowledge base response back to OpenAI")
                                    await openai_ws.send(json.dumps(tool_response))
                            except Exception as e:
                                print(f"Error handling function call: {e}")
                                import traceback
                                print(traceback.format_exc())

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
                "tools": [
                    {
                        "type": "function",
                        "name": "search_knowledge_base",
                        "description": "Search the knowledge base for information to answer user questions",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The user's question to search for in the knowledge base"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                ]
            }
        }
        print("Initializing OpenAI session with config:", json.dumps(session_config, indent=2))
        await openai_ws.send(json.dumps(session_config)) 