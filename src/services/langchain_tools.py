import json
import asyncio
from typing import Dict, Any, Optional, Type
from pydantic import BaseModel, Field
from fastapi import WebSocket

from langchain.tools import BaseTool

class SearchKnowledgeInput(BaseModel):
    query: str = Field(description="The user's question to search for in the knowledge base")

class EndCallInput(BaseModel):
    reason: str = Field(description="The reason for ending the call: 'question_answered' or 'insufficient_information'")

class SendInstructionInput(BaseModel):
    instruction: str = Field(description="The instruction to send to the model to guide its response")

class SendInterimMessageInput(BaseModel):
    message: str = Field(description="An interim message to send to the user while processing")

class HandleInterruptionInput(BaseModel):
    acknowledge: bool = Field(description="Whether to acknowledge the interruption", default=True)

class InitiateGreetingInput(BaseModel):
    custom_greeting: Optional[str] = Field(description="Optional custom greeting message", default=None)

class SearchKnowledgeBaseTool(BaseTool):
    name: str = "search_knowledge_base"
    description: str = "Search the knowledge base for information to answer user questions"
    args_schema: Type[BaseModel] = SearchKnowledgeInput
    
    # Define these as class variables for Pydantic
    knowledge_service: Any = None
    openai_ws: Any = None
    send_instruction_tool: Any = None
    
    def __init__(self, knowledge_service, openai_ws):
        super().__init__()
        self.knowledge_service = knowledge_service
        self.openai_ws = openai_ws
        self.send_instruction_tool = SendInstructionTool(openai_ws)
        
    async def _arun(self, query: str) -> str:
        """Async implementation of the knowledge base search"""
        print(f"Searching knowledge base for: {query}")
        
        # Send an interim message that we're searching
        await self.send_instruction_tool._arun("Let me check our knowledge base for information about that.")
        
        # Get answer from knowledge base
        kb_response = self.knowledge_service.get_kb_answer(query)
        
        # Send the response using the instruction tool
        await self.send_instruction_tool._arun(kb_response + "\n\nAfter providing this information, ask 'Did that answer your question?'")
        
        return f"Knowledge base search completed for '{query}'. Response sent to user."
    
    def _run(self, query: str) -> str:
        """Synchronous implementation - this will create an event loop if needed"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._arun(query))

class EndCallTool(BaseTool):
    name: str = "end_call"
    description: str = "End the current call with a reason"
    args_schema: Type[BaseModel] = EndCallInput
    
    # Define class variables for Pydantic
    websocket: Any = None
    openai_ws: Any = None
    stream_sid: Any = None
    conversation_service: Any = None
    send_instruction_tool: Any = None
    
    def __init__(self, websocket, openai_ws, stream_sid, conversation_service):
        super().__init__()
        self.websocket = websocket
        self.openai_ws = openai_ws
        self.stream_sid = stream_sid
        self.conversation_service = conversation_service
        self.send_instruction_tool = SendInstructionTool(openai_ws)
        
    async def _arun(self, reason: str) -> str:
        """Async implementation of the end call function"""
        print(f"Ending call with reason: {reason}")
        
        try:
            # Send final message before ending call
            farewell_message = "Thank you for calling. Have a great day!"
            
            # Use the SendInstructionTool to send the farewell message
            await self.send_instruction_tool._arun(farewell_message)
            
            # Wait for the audio to be generated and sent
            await asyncio.sleep(3)
            
            # No need to save the conversation here as it's done in the stop event handler
            
            # Send stop event to Twilio
            print(f"Sending stop event for stream: {self.stream_sid}")
            await self.websocket.send_json({
                "event": "stop",
                "streamSid": self.stream_sid
            })
            
            # Close the OpenAI WebSocket connection
            if self.openai_ws.open:
                await self.openai_ws.close()
            
            return "Call ended successfully"
            
        except Exception as e:
            print(f"Error ending call: {e}")
            import traceback
            print(traceback.format_exc())
            
            # Attempt to close connections even if there was an error
            try:
                if self.websocket:
                    await self.websocket.send_json({
                        "event": "stop",
                        "streamSid": self.stream_sid
                    })
            except:
                pass
            
            try:
                if self.openai_ws and self.openai_ws.open:
                    await self.openai_ws.close()
            except:
                pass
            
            return f"Error ending call: {str(e)}"
    
    def _run(self, reason: str) -> str:
        """Synchronous implementation - this will create an event loop if needed"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._arun(reason))

class SendInstructionTool(BaseTool):
    name: str = "send_instruction"
    description: str = "Send an instruction to the OpenAI API"
    args_schema: Type[BaseModel] = SendInstructionInput
    
    # Define class variable for Pydantic
    openai_ws: Any = None
    
    def __init__(self, openai_ws):
        super().__init__()
        self.openai_ws = openai_ws
    
    async def _arun(self, instruction: str) -> str:
        """Async implementation of the instruction sending"""
        print(f"Sending instruction: {instruction}")
        
        # Create the instruction message
        instruction_message = {
            "type": "response.create",
            "response": {
                "instructions": instruction
            }
        }
        
        # Send the instruction to OpenAI
        await self.openai_ws.send(json.dumps(instruction_message))
        
        return f"Instruction sent: {instruction}"
    
    def _run(self, instruction: str) -> str:
        """Synchronous implementation - this will create an event loop if needed"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._arun(instruction))

class SendInterimMessageTool(BaseTool):
    name: str = "send_interim_message"
    description: str = "Send an interim message to the user while processing"
    args_schema: Type[BaseModel] = SendInterimMessageInput
    
    def __init__(self, openai_ws):
        super().__init__()
        self.openai_ws = openai_ws
        self.send_instruction_tool = SendInstructionTool(openai_ws)
        
    async def _arun(self, message: str) -> str:
        """Async implementation of sending interim message"""
        print(f"Sending interim message: {message}")
        
        # Use the SendInstructionTool
        await self.send_instruction_tool._arun(message)
        
        return f"Interim message sent: {message}"
    
    def _run(self, message: str) -> str:
        """Synchronous implementation - this will create an event loop if needed"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._arun(message))

class HandleInterruptionTool(BaseTool):
    name: str = "handle_interruption"
    description: str = "Handle user interruption during assistant's response"
    args_schema: Type[BaseModel] = HandleInterruptionInput
    
    def __init__(self, websocket, openai_ws, stream_sid):
        super().__init__()
        self.websocket = websocket
        self.openai_ws = openai_ws
        self.stream_sid = stream_sid
        self.last_assistant_item = None
        self.elapsed_time = 0
        
    def update_context(self, last_assistant_item, elapsed_time):
        """Update the context for handling interruptions"""
        self.last_assistant_item = last_assistant_item
        self.elapsed_time = elapsed_time
        
    async def _arun(self, acknowledge: bool = True) -> str:
        """Async implementation of handling interruption"""
        if not self.last_assistant_item:
            return "No assistant item to interrupt"
            
        print(f"Handling interruption for item: {self.last_assistant_item}")
        
        # Truncate the current response
        truncate_event = {
            "type": "conversation.item.truncate",
            "item_id": self.last_assistant_item,
            "content_index": 0,
            "audio_end_ms": self.elapsed_time
        }
        await self.openai_ws.send(json.dumps(truncate_event))
        
        # Clear the audio queue
        await self.websocket.send_json({
            "event": "clear",
            "streamSid": self.stream_sid
        })
        
        # Send instruction to acknowledge interruption if requested
        if acknowledge:
            instruction_message = {
                "type": "response.create",
                "response": {
                    "instructions": "The user interrupted. Acknowledge this and respond to their new input."
                }
            }
            await self.openai_ws.send(json.dumps(instruction_message))
            
        return "Interruption handled successfully"
    
    def _run(self, acknowledge: bool = True) -> str:
        """Synchronous implementation - this will create an event loop if needed"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._arun(acknowledge))

class InitiateGreetingTool(BaseTool):
    name: str = "initiate_greeting"
    description: str = "Send initial greeting to start the conversation"
    args_schema: Type[BaseModel] = InitiateGreetingInput
    
    def __init__(self, openai_ws):
        super().__init__()
        self.openai_ws = openai_ws
        
    async def _arun(self, custom_greeting: Optional[str] = None) -> str:
        """Async implementation of sending initial greeting"""
        greeting = custom_greeting or "Hi! This is Kai speaking. How can I assist you?"
        print(f"Sending initial greeting: {greeting}")
        
        initial_conversation_item = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Greet the user with '{greeting}'"
                    }
                ]
            }
        }
        
        await self.openai_ws.send(json.dumps(initial_conversation_item))
        await self.openai_ws.send(json.dumps({"type": "response.create"}))
        
        return "Initial LC greeting sent"
    
    def _run(self, custom_greeting: Optional[str] = None) -> str:
        """Synchronous implementation - this will create an event loop if needed"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._arun(custom_greeting)) 