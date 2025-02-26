import json
from typing import Dict, Any
import asyncio
from fastapi import WebSocket
from .search_service import KnowledgeBaseSearchService
from .auth_service import KayakoAuthService
from .ticket_service import KayakoTicketService

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
                await self._handle_end_call(websocket, openai_ws, stream_sid)
                
            elif function_name == 'search_knowledge_base':
                await self._handle_knowledge_base_search(function_args, call_id, openai_ws)
                
        except Exception as e:
            print(f"Error handling function call: {e}")
            import traceback
            print(traceback.format_exc())
    
    async def _handle_end_call(self, websocket: WebSocket, openai_ws: WebSocket, stream_sid: str) -> None:
        """Handle the end_call function"""
        print("Ending call, thanks for calling")
        # Send final message before ending call
        tool_response = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "Ending call, thanks for calling"
                    }
                ]
            }
        }
        await openai_ws.send(json.dumps(tool_response))
        await openai_ws.send(json.dumps({"type": "response.create"}))
        
        # Wait a moment for the message to be processed
        await asyncio.sleep(2)
        
        # Then end the call
        await websocket.send_json({
            "event": "stop",
            "streamSid": stream_sid
        })
        if openai_ws.open:
            await openai_ws.close()
    
    async def _handle_knowledge_base_search(self, function_args: str, call_id: str, openai_ws: WebSocket) -> None:
        """Handle the search_knowledge_base function"""
        args = json.loads(function_args)
        kb_response = self.knowledge_base_service.get_kb_answer(args['query'])
        
        # Send tool response back to OpenAI
        tool_response = {
            "type": "response.create",
            "response": {
                "instructions": kb_response
            }
        }
        
        print("Sending knowledge base response back to OpenAI")
        await openai_ws.send(json.dumps(tool_response)) 