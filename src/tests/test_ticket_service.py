import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.services.ticket_service import KayakoTicketService
from src.services.auth_service import KayakoAuthService

def test_make_ticket():
    # Mock conversation data
    mock_conversation = [
        {"role": "assistant", "content": "Hi! This is Kai speaking. How can I assist you?"},
        {"role": "caller", "content": "I'm having trouble with my coffee machine"},
        {"role": "assistant", "content": "I understand you're having issues with your coffee machine. Let me check our knowledge base."},
        {"role": "assistant", "content": "Based on our information, the most common issues with coffee machines are related to clogging or improper water flow. Have you tried descaling your machine? Did that answer your question?"},
        {"role": "caller", "content": "Yes, that helps"},
        {"role": "assistant", "content": "Great! Do you have any other questions I can help you with?"},
        {"role": "caller", "content": "No, that's all"},
        {"role": "assistant", "content": "Thank you for calling. Have a great day!"}
    ]

    # Mock phone number
    mock_phone_number = "+1234567890"

    # Initialize services
    auth_service = KayakoAuthService()
    ticket_service = KayakoTicketService(auth_service)

    # Create ticket
    try:
        ticket = ticket_service.make_ticket(mock_conversation, mock_phone_number)
        
        if ticket:
            print("\nTicket created successfully!")
            print(f"Ticket ID: {ticket.get('id', 'N/A')}")
            print(f"Subject: {ticket.get('subject', 'N/A')}")
            print(f"Status: {ticket.get('status', 'N/A')}")
        else:
            print("\nFailed to create ticket")
            
    except Exception as e:
        print(f"\nError creating ticket: {e}")

if __name__ == "__main__":
    test_make_ticket() 