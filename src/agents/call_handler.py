from typing import Dict, Any
from src.agents.base import BaseAgent

class CallHandlerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="call_handler")
        self.current_call_sid = None
        
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming call data and return appropriate response"""
        # Store call SID if present
        if 'CallSid' in input_data:
            self.current_call_sid = input_data['CallSid']
            self.update_state({"call_sid": self.current_call_sid})
        
        # Basic response for now
        return {
            "action": "respond",
            "message": "Thank you for your call. How can I assist you today?"
        } 