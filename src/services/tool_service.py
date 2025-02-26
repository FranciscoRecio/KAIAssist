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
        
        try:
            # Send final message before ending call
            farewell_message = "Thank you for calling. Have a great day!"
            
            # Create a conversation item with the farewell message
            tool_response = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": farewell_message
                        }
                    ]
                }
            }
            
            # Send the message to OpenAI
            await openai_ws.send(json.dumps(tool_response))
            
            # Request OpenAI to generate a response (including audio)
            await openai_ws.send(json.dumps({"type": "response.create"}))
            
            # Wait for the audio to be generated and sent
            # This is more reliable than a fixed sleep
            await asyncio.sleep(3)
            
            # Save the conversation before ending the call
            if conversation_service and stream_sid:
                print(f"Saving conversation for stream: {stream_sid}")
                conversation_service.save_conversation(stream_sid)
            
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
            
            # Save the conversation even if there's an error
            try:
                if conversation_service and stream_sid:
                    print(f"Saving conversation after error for stream: {stream_sid}")
                    conversation_service.save_conversation(stream_sid)
            except Exception as save_error:
                print(f"Error saving conversation: {save_error}")
            
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
        
        # Send an interim message that we're searching
        await self._send_interim_message(openai_ws, "Let me check our knowledge base for information about that.")
        
        # Perform the search
        kb_response = self.knowledge_base_service.get_kb_answer(args['query'])
        
        # Send tool response back to OpenAI
        tool_response = {
            "type": "response.create",
            "response": {
                "instructions": kb_response + "\n\nAfter providing this information, ask 'Did that answer your question?'"
            }
        }
        
        print("Sending knowledge base response back to OpenAI")
        await openai_ws.send(json.dumps(tool_response))

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
        tool_response = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": message
                    }
                ]
            }
        }
        await openai_ws.send(json.dumps(tool_response))

    async def _send_instruction(self, openai_ws: WebSocket, instruction: str) -> None:
        """Send an instruction to guide the model's response"""
        instruction_message = {
            "type": "response.create",
            "response": {
                "instructions": instruction
            }
        }
        await openai_ws.send(json.dumps(instruction_message))

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
        """Enforce the conversation flow based on the current state"""
        # Skip if stream_sid is None (call not yet started)
        if not stream_sid:
            return
        
        conversation = conversation_service.get_conversation(stream_sid)
        if not conversation:
            return
        
        # Get the last few messages to determine context
        recent_messages = [msg for msg in conversation if msg.get('role') in ['caller', 'assistant']]
        if len(recent_messages) < 1:
            return
        
        recent_messages = recent_messages[-3:]  # Get last 3 messages
        
        print(f"Enforcing conversation flow for state: {current_state}")
        
        if current_state == "initial_response":
            # After initial KB search, ensure we ask if it answered their question
            await self._send_instruction(openai_ws, "After providing the information, ask 'Did that answer your question?'")
        
        elif current_state == "awaiting_answer_feedback":
            # Check if caller said yes or no to "Did that answer your question?"
            last_caller_msg = next((msg for msg in reversed(recent_messages) if msg.get('role') == 'caller'), None)
            
            if last_caller_msg:
                response_text = last_caller_msg.get('content', '').lower()
                if any(word in response_text for word in ['no', "didn't", 'not']):
                    # If no, instruct to apologize and end call
                    await self._send_instruction(openai_ws, 
                        "Say: 'I apologize, but I don't have enough information to fully answer your question. "
                        "I'll have a representative call you back to assist with this. Thank you for calling.'")
                    # Update state to prepare for ending call
                    conversation_service.update_call_state(stream_sid, "ending_insufficient_info")
                else:
                    # If yes, ask if they have other questions
                    await self._send_instruction(openai_ws, "Ask: 'Do you have any other questions I can help you with?'")
                    conversation_service.update_call_state(stream_sid, "awaiting_more_questions")
        
        elif current_state == "awaiting_more_questions":
            # Check if caller has more questions
            last_caller_msg = next((msg for msg in reversed(recent_messages) if msg.get('role') == 'caller'), None)
            
            if last_caller_msg:
                response_text = last_caller_msg.get('content', '').lower()
                if any(word in response_text for word in ['no', 'nope', "that's all", 'nothing']):
                    # If no more questions, end call
                    await self._send_instruction(openai_ws, 
                        "Say: 'Thank you for calling. Have a great day!' Then end the call.")
                    conversation_service.update_call_state(stream_sid, "ending_question_answered")
                else:
                    # If they have more questions, restart the flow
                    conversation_service.update_call_state(stream_sid, "initial_response")
        
        elif current_state in ["ending_question_answered", "ending_insufficient_info"]:
            # Handle specific ending states
            if websocket:  # Only proceed if websocket is provided
                args = json.dumps({"reason": "question_answered" if current_state == "ending_question_answered" else "insufficient_information"})
                await self.handle_function_call("end_call", args, "auto_end", websocket, openai_ws, stream_sid, conversation_service) 

    async def _send_initial_greeting(self, openai_ws: WebSocket) -> None:
        """Send initial greeting to start the conversation."""
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