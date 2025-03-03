import json
from services.ticket_agent_service import TicketAgentService

def main():
    # Create a sample conversation
    test_conversation = [
        {"role": "assistant", "content": "Hi! This is Kai speaking. How can I assist you today?"},
        {"role": "caller", "content": "I'm having trouble logging into my account. I keep getting an error message."},
        {"role": "assistant", "content": "I understand you're having trouble logging in. Let me search for information about login issues."},
        {"role": "assistant", "content": "Based on our knowledge base, there are a few common reasons for login issues:\n\n1. Incorrect username or password\n2. Account might be locked after too many failed attempts\n3. Browser cache or cookies issues\n4. System maintenance\n\nCould you tell me what error message you're seeing?"},
        {"role": "caller", "content": "It says 'Invalid credentials' but I'm sure my password is correct."},
        {"role": "assistant", "content": "Thank you for that information. For 'Invalid credentials' errors, I recommend trying these steps:\n\n1. Double-check your username and password for typos\n2. Try the 'Forgot Password' option to reset your password\n3. Clear your browser cache and cookies\n4. Try using a different browser\n\nDid that answer your question?"},
        {"role": "caller", "content": "Yes, I'll try resetting my password."},
        {"role": "assistant", "content": "Great! To reset your password, go to the login page and click on 'Forgot Password'. You'll receive an email with instructions to create a new password.\n\nDo you have any other questions I can help you with?"},
        {"role": "caller", "content": "No, that's all. Thank you!"},
        {"role": "assistant", "content": "You're welcome! Thank you for calling. Have a great day!"}
    ]
    
    # Add some metadata to test filtering
    test_conversation.append({
        "metadata": {
            "state": "ending",
            "state_updated_at": "2023-12-01T12:00:00Z"
        }
    })
    
    # Create the ticket agent
    ticket_agent = TicketAgentService()
    
    # Process the conversation
    print("Processing test conversation...")
    result = ticket_agent.process_conversation(test_conversation, caller_number="+1234567890")
    
    # Print the results
    print("\n=== TICKET RESULT ===")
    print(f"Subject: {result['subject']}")
    print("\nContents:")
    print(result['contents'])
    
    # Print resolution status in a readable format
    print("\nResolution Status:")
    if isinstance(result['resolution_status'], dict):
        print(json.dumps(result['resolution_status'], indent=2))
    else:
        print(result['resolution_status'])
    
    print("=== END TICKET RESULT ===")

if __name__ == "__main__":
    main() 