from typing import Dict, Optional, List
import requests
from .auth_service import KayakoAuthService
from datetime import datetime

class KayakoTicketService:
    def __init__(self, auth_service: KayakoAuthService):
        self.auth_service = auth_service
        self.base_url = auth_service.base_url
    
    def create_ticket(self, 
                     subject: str,
                     contents: str,
                     requester_id: str,
                     channel: str = "MAIL",
                     channel_id: str = "1",
                     priority_id: str = "3",
                     type_id: str = "1") -> Optional[Dict]:
        """
        Create a new ticket in Kayako
        
        Args:
            subject (str): The ticket subject
            contents (str): The ticket description/content
            requester_id (str): The ID of the person requesting the ticket
            channel (str, optional): The channel type. Defaults to "MAIL"
            channel_id (str, optional): The channel ID. Defaults to "1"
            priority_id (str, optional): The priority level ID. Defaults to "3"
            type_id (str, optional): The ticket type ID. Defaults to "1"
            
        Returns:
            Dict or None: The created ticket data if successful, None if failed
        """
        url = f"{self.base_url}/cases"
        
        payload = {
            "subject": subject,
            "contents": contents,
            "channel": channel,
            "channel_id": channel_id,
            "requester_id": requester_id,
            "priority_id": priority_id,
            "type_id": type_id
        }
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers=self.auth_service.get_auth_headers()
            )
            response.raise_for_status()
            return response.json().get('data')
            
        except requests.exceptions.HTTPError as e:
            print(f"Error creating ticket: {e.response.status_code}")
            print(f"Response: {e.response.text}")
            return None
        except Exception as e:
            print(f"Error creating ticket: {e}")
            return None 

    def make_ticket(self, conversation: List[Dict], phone_number: str) -> Optional[Dict]:
        """
        Create a ticket from a conversation history and phone number
        
        Args:
            conversation (List[Dict]): List of conversation messages with 'role' and 'content'
            phone_number (str): The caller's phone number
            
        Returns:
            Dict or None: The created ticket data if successful, None if failed
        """
        try:
            # Format the conversation into a readable format
            formatted_conversation = []
            for msg in conversation:
                role = "Caller" if msg['role'] == 'caller' else "Assistant"
                formatted_conversation.append(f"{role}: {msg['content']}")
            
            conversation_text = "\n".join(formatted_conversation)
            
            # Create a descriptive subject from the first user message
            user_messages = [msg['content'] for msg in conversation if msg['role'] == 'user']
            subject = user_messages[0] if user_messages else "Phone conversation ticket"
            if len(subject) > 50:  # Truncate if too long
                subject = subject[:47] + "..."
            
            # Format the contents with conversation and metadata
            contents = f"""Phone Call Conversation Log
Caller Phone Number: {phone_number}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Conversation:
{conversation_text}"""

            # Create the ticket using default values
            return self.create_ticket(
                subject=subject,
                contents=contents,
                requester_id="2",  # Default requester ID
            )
            
        except Exception as e:
            print(f"Error creating ticket from conversation: {e}")
            return None 