from typing import Dict, Optional, List
import requests
from .auth_service import KayakoAuthService
from datetime import datetime
from .ticket_agent_service import TicketAgentService

class KayakoTicketService:
    def __init__(self, auth_service: KayakoAuthService):
        self.auth_service = auth_service
        self.base_url = auth_service.base_url
        self.ticket_agent = TicketAgentService()
    
    def create_ticket(self, 
                     subject: str,
                     contents: str,
                     requester_id: int,
                     channel: str = "MAIL",
                     channel_id: int = 1,
                     priority_id: int = 3,
                     type_id: int = 1) -> Optional[Dict]:
        """
        Create a new ticket in Kayako
        
        Args:
            subject (str): The ticket subject
            contents (str): The ticket description/content
            requester_id (int): The ID of the person requesting the ticket
            channel (str, optional): The channel type. Defaults to "MAIL"
            channel_id (int, optional): The channel ID. Defaults to 1
            priority_id (int, optional): The priority level ID. Defaults to 3
            type_id (int, optional): The ticket type ID. Defaults to 1
            
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
        """Create a ticket from the conversation"""
        try:
            # Use the ticket agent to process the conversation
            ticket_data = self.ticket_agent.process_conversation(conversation, phone_number)
            
            # Extract the subject and contents
            subject = ticket_data.get('subject', 'Call with AI Assistant')
            contents = ticket_data.get('contents', '')
            
            # Print the subject and contents for testing
            print("\n==== TICKET INFORMATION ====")
            print(f"SUBJECT: {subject}")
            print("\nCONTENTS:")
            print(contents)
            print("==== END TICKET INFORMATION ====\n")
            
            # For testing, just return a mock ticket response instead of creating a real ticket
            return {
                "id": 12345,
                "subject": subject,
                "status": "TEST_TICKET - Not actually created",
                "resolution_status": ticket_data.get('resolution_status')
            }
        except Exception as e:
            print(f"Error creating ticket from conversation: {e}")
            import traceback
            print(traceback.format_exc())
            return None 