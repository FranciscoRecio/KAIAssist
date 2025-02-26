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
    
    def update_call_state(self, stream_sid: str, state: str) -> None:
        """Update the state of the conversation"""
        if not stream_sid:
            return  # Skip if stream_sid is not yet available
        
        if stream_sid not in self.active_conversations:
            self.start_conversation(stream_sid)
        
        # Check if we already have metadata in the conversation
        metadata_exists = False
        for item in self.active_conversations[stream_sid]:
            if 'metadata' in item:
                item['metadata']['state'] = state
                item['metadata']['state_updated_at'] = datetime.utcnow().isoformat()
                metadata_exists = True
                break
        
        # If no metadata exists, add it
        if not metadata_exists:
            self.active_conversations[stream_sid].append({
                'metadata': {
                    'state': state,
                    'state_updated_at': datetime.utcnow().isoformat()
                }
            })
        
        print(f"Call state updated: {state}")

    def get_call_state(self, stream_sid: str) -> str:
        """Get the current state of the conversation"""
        if not stream_sid or stream_sid not in self.active_conversations:
            return "initial"
        
        for item in self.active_conversations[stream_sid]:
            if 'metadata' in item and 'state' in item['metadata']:
                return item['metadata']['state']
        
        return "initial" 