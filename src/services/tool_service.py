import json
from typing import Dict, Any
import asyncio
from fastapi import WebSocket
from .search_service import KnowledgeBaseSearchService
from .auth_service import KayakoAuthService
from .ticket_service import KayakoTicketService

class CallState:
    INITIAL = "initial"
    SEARCHING_KB = "searching_kb"
    ANSWERING = "answering"
    CONFIRMING = "awaiting_answer_feedback"
    FOLLOW_UP = "awaiting_more_questions"
    ENDING = "ending"
    ENDING_QUESTION_ANSWERED = "ending_question_answered"
    ENDING_INSUFFICIENT_INFO = "ending_insufficient_info"

class ToolService:
    def __init__(self):
        self.knowledge_base_service = KnowledgeBaseSearchService()
    
    async def handle_function_call(self, 
                                 function_name: str, 
                                 function_args: str, 
                                 call_id: str,
                                 websocket: WebSocket,
                                 openai_ws: WebSocket,
                                 stream_sid: str,
                                 conversation_service,
                                 caller_number: str = None) -> None:
        """Handle function calls from the OpenAI API"""
        try:
            print(f"\nFunction called: {function_name}")
            print(f"Arguments: {function_args}")
            
            if function_name == 'end_call':
                await self._handle_end_call(websocket, openai_ws, stream_sid, conversation_service)
                
            elif function_name == 'search_knowledge_base':
                await self._handle_knowledge_base_search(function_args, call_id, openai_ws)
                
        except Exception as e:
            print(f"Error handling function call: {e}")
            import traceback
            print(traceback.format_exc())
    
    async def _handle_end_call(self, websocket: WebSocket, openai_ws: WebSocket, stream_sid: str, conversation_service=None) -> None:
        """Handle the end_call function"""
        print("Ending call, thanks for calling")
        
        # Add a check to prevent duplicate end_call handling
        if conversation_service:
            current_state = conversation_service.get_call_state(stream_sid)
            if current_state == "ending":
                print("Call already ending, skipping duplicate end_call")
                return
            conversation_service.update_call_state(stream_sid, "ending")
        
        try:
            # # Send final message before ending call using the format that works
            # farewell_instruction = "Say: 'Thank you for calling Kayako. Have a great day!'"
            
            # # Use the response.create format that works for other messages
            # farewell_response = {
            #     "type": "response.create",
            #     "response": {
            #         "instructions": farewell_instruction
            #     }
            # }
            
            # # Send the message to OpenAI
            # await openai_ws.send(json.dumps(farewell_response))
            
            # Wait for the audio to be generated and sent
            # This is more reliable than a fixed sleep
            await asyncio.sleep(3)
            
            # Send stop event to Twilio
            print(f"Sending stop event for stream: {stream_sid}")
            await websocket.send_json({
                "event": "stop",
                "streamSid": stream_sid
            })
            
            # Close the OpenAI WebSocket connection
            if openai_ws.open:
                await openai_ws.close()
            
            print("Call ended successfully")
            
        except Exception as e:
            print(f"Error ending call: {e}")
            import traceback
            print(traceback.format_exc())
            
            # Attempt to close connections even if there was an error
            try:
                if websocket:
                    await websocket.send_json({
                        "event": "stop",
                        "streamSid": stream_sid
                    })
            except:
                pass
            
            try:
                if openai_ws and openai_ws.open:
                    await openai_ws.close()
            except:
                pass
    
    async def _handle_knowledge_base_search(self, function_args: str, call_id: str, openai_ws: WebSocket) -> None:
        """Handle the search_knowledge_base function with progress updates"""
        args = json.loads(function_args)
        
        try:
            # Perform the search directly without interim message
            kb_response = self.knowledge_base_service.get_kb_answer(args['query'])
            
            # Send tool response back to OpenAI - USING THE ORIGINAL FORMAT
            tool_response = {
                "type": "response.create",
                "response": {
                    "instructions": kb_response + "\n\nAfter providing this information, ask 'Did that answer your question?'"
                }
            }
            
            print("Sending knowledge base response back to OpenAI")
            await openai_ws.send(json.dumps(tool_response))
        except Exception as e:
            print(f"Error in knowledge base search: {e}")
            import traceback
            print(traceback.format_exc())

    async def control_call_flow(self, 
                               current_state: str,
                               next_state: str,
                               call_id: str,
                               websocket: WebSocket,
                               openai_ws: WebSocket,
                               stream_sid: str,
                               conversation_service) -> None:
        """Control the flow of the call based on state transitions"""
        print(f"Call flow transition: {current_state} -> {next_state}")
        
        # Handle state transitions
        if current_state == "none" and next_state == CallState.INITIAL:
            # Initial greeting when call starts
            await self._send_initial_greeting(openai_ws)
        
        elif current_state == CallState.INITIAL and next_state == CallState.SEARCHING_KB:
            # Notify user that we're searching
            await self._send_interim_message(openai_ws, "I'm searching our knowledge base for information...")
        
        elif current_state == CallState.SEARCHING_KB and next_state == CallState.ANSWERING:
            # This transition happens after KB search completes
            pass
        
        elif next_state == CallState.CONFIRMING:
            # Ensure we always ask if the answer was helpful
            await self._send_instruction(openai_ws, "Ask the caller if the information answered their question.")
        
        elif next_state == CallState.FOLLOW_UP:
            # Ensure we ask if they have more questions
            await self._send_instruction(openai_ws, "Ask the caller if they have any other questions.")
        
        elif next_state == CallState.ENDING:
            # Begin call termination process
            await self._handle_end_call(websocket, openai_ws, stream_sid, conversation_service)
        
        # Update conversation state
        conversation_service.update_call_state(stream_sid, next_state) 

    async def _send_interim_message(self, openai_ws: WebSocket, message: str) -> None:
        """Send an interim message to the caller while processing"""
        try:
            print(f"Sending interim message: {message}")
            
            # Use the original format for sending interim messages
            interim_message = {
                "type": "response.create",
                "response": {
                    "instructions": message
                }
            }
            
            await openai_ws.send(json.dumps(interim_message))
            
            # Wait a moment to ensure the message is processed
            await asyncio.sleep(1)
            print("Interim message sent")
        except Exception as e:
            print(f"Error sending interim message: {e}")
            import traceback
            print(traceback.format_exc())

    async def _send_instruction(self, openai_ws: WebSocket, instruction: str) -> None:
        """Send an instruction to OpenAI"""
        try:
            print(f"Sending instruction: {instruction}")
            
            # Use the original format for sending instructions
            instruction_payload = {
                "type": "response.create",
                "response": {
                    "instructions": instruction
                }
            }
            
            # Send the instruction to OpenAI
            await openai_ws.send(json.dumps(instruction_payload))
        except Exception as e:
            print(f"Error sending instruction: {e}")

    async def handle_interruption(self, 
                                 websocket: WebSocket, 
                                 openai_ws: WebSocket, 
                                 stream_sid: str,
                                 last_assistant_item: str,
                                 elapsed_time: int) -> None:
        """Handle user interruption during assistant's response"""
        # Truncate the current response
        truncate_event = {
            "type": "conversation.item.truncate",
            "item_id": last_assistant_item,
            "content_index": 0,
            "audio_end_ms": elapsed_time
        }
        await openai_ws.send(json.dumps(truncate_event))
        
        # Clear the audio queue
        await websocket.send_json({
            "event": "clear",
            "streamSid": stream_sid
        })
        
        # Send instruction to acknowledge interruption
        await self._send_instruction(openai_ws, "The user interrupted. Acknowledge this and respond to their new input.") 

    async def enforce_conversation_flow(self, 
                                      current_state: str,
                                      conversation_service,
                                      stream_sid: str,
                                      openai_ws: WebSocket,
                                      websocket: WebSocket = None) -> None:
        # Skip if stream_sid is None (call not yet started)
        if not stream_sid:
            return
        
        # Check if we're in a state where we should avoid sending new instructions
        if current_state in ["ending", "ending_question_answered", "ending_insufficient_info"]:
            print("Call is ending, skipping further instructions")
            return
        
        try:
            # Get recent messages to determine context
            conversation = conversation_service.get_conversation(stream_sid)
            if not conversation:
                print("No conversation data available")
                return
            
            recent_messages = [msg for msg in conversation if msg.get('role') in ['caller', 'assistant']][-3:] if conversation else []
            
            # Different actions based on current state
            if current_state == "awaiting_answer_feedback":
                # Check if user indicated the answer was helpful or not
                if recent_messages and recent_messages[-1].get('role') == 'caller':
                    user_message = recent_messages[-1].get('content', '').lower()
                    
                    # Check for positive responses
                    if any(word in user_message for word in ['yes', 'yeah', 'correct', 'right', 'good', 'helpful', 'thanks']):
                        print("User indicated the answer was helpful, asking for more questions")
                        
                        # Update state first
                        conversation_service.update_call_state(stream_sid, "awaiting_more_questions")
                        
                        # Then send the instruction
                        await self._send_instruction(openai_ws, "Ask: 'Do you have any other questions I can help you with?'")
                        
                    # Check for negative responses
                    elif any(word in user_message for word in ['no', "didn't", 'not', 'nope']):
                        print("User indicated the answer was not helpful, ending call")
                        
                        # Update state first
                        conversation_service.update_call_state(stream_sid, "ending_insufficient_info")
                        
                        # Then send the instruction with proper formatting
                        instruction = "Say: 'I apologize, but I don't have enough information to fully answer your question. I'll have a representative call you back to assist with this. Thank you for calling.'"
                        await self._send_instruction(openai_ws, instruction)
                        
                        # End the call without delay
                        await self._handle_end_call(websocket, openai_ws, stream_sid, conversation_service)
                    else:
                        # Ambiguous response, ask for clarification
                        print("User response was ambiguous, asking for clarification")
                        await self._send_instruction(openai_ws, "Ask again if the information answered their question.")
            
            elif current_state == "awaiting_more_questions":
                # Check if user has more questions
                if recent_messages and recent_messages[-1].get('role') == 'caller':
                    user_message = recent_messages[-1].get('content', '').lower()
                    
                    if any(word in user_message for word in ['no', 'nope', "that's all", 'nothing', 'done']):
                        print("User has no more questions, ending call")
                        
                        # Update state first
                        conversation_service.update_call_state(stream_sid, "ending_question_answered")
                        
                        # Then send the instruction
                        await self._send_instruction(openai_ws, "Say: 'Thank you for calling. Have a great day!'")
                        
                        # End the call without delay
                        await self._handle_end_call(websocket, openai_ws, stream_sid, conversation_service)
                    else:
                        # User has more questions, let the model handle it
                        print("User has more questions, continuing conversation")
                        # Reset state to initial to handle the new question
                        conversation_service.update_call_state(stream_sid, "initial")
        except Exception as e:
            print(f"Error enforcing conversation flow: {e}")
            import traceback
            print(traceback.format_exc())

    async def _send_initial_greeting(self, openai_ws: WebSocket) -> None:
        """Send initial greeting to start the conversation."""
        try:
            print("Sending initial greeting")
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
            print("Initial greeting sent")
        except Exception as e:
            print(f"Error sending initial greeting: {e}")
            import traceback
            print(traceback.format_exc())

    async def _send_initial_greeting(self, openai_ws: WebSocket) -> None:
        """Send initial greeting to start the conversation."""
        try:
            print("Sending initial greeting")
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
            print("Initial greeting sent")
        except Exception as e:
            print(f"Error sending initial greeting: {e}")
            import traceback
            print(traceback.format_exc()) 