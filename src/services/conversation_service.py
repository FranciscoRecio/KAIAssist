from typing import List, Dict
import json
from datetime import datetime

class ConversationService:
    def __init__(self):
        self.active_conversations: Dict[str, List[Dict]] = {}
    
    def start_conversation(self, stream_sid: str) -> None:
        """Initialize a new conversation"""
        self.active_conversations[stream_sid] = []
        
    def add_message(self, stream_sid: str, role: str, content: str) -> None:
        """Add a message to the conversation"""
        if stream_sid not in self.active_conversations:
            self.start_conversation(stream_sid)
            
        self.active_conversations[stream_sid].append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def get_conversation(self, stream_sid: str) -> List[Dict]:
        """Get the full conversation history"""
        return self.active_conversations.get(stream_sid, [])
    
    def save_conversation(self, stream_sid: str) -> None:
        """Print out the conversation"""
        if stream_sid in self.active_conversations:
            conversation = self.active_conversations[stream_sid]
            print("\nFinal Conversation:")
            for message in conversation:
                print(f"{message['role'].title()}: {message['content']}")
                print(f"Timestamp: {message['timestamp']}\n")
            
            # Clean up the active conversation
            del self.active_conversations[stream_sid] 