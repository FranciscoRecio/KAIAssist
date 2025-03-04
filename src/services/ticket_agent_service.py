from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import Tool
from langchain.schema import SystemMessage
from typing import List, Dict, Optional, Any
import os
import re
from dotenv import load_dotenv

class TicketAgentService:
    def __init__(self):
        load_dotenv()
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.2,
            api_key=os.getenv('OPENAI_API_KEY')
        )
        
        # Define tools using the Tool class
        self.tools = [
            Tool(
                name="summarize_conversation",
                func=self.summarize_conversation,
                description="Summarize the key points of a conversation"
            ),
            Tool(
                name="create_ticket_subject",
                func=self.create_ticket_subject,
                description="Create a clear and concise subject line for the ticket"
            ),
            Tool(
                name="determine_resolution_status",
                func=self.determine_resolution_status,
                description="Determine if the issue was resolved during the call"
            )
        ]
        
        # Create the agent
        self.agent = self._create_agent()
    
    def _create_agent(self):
        """Create a Langchain agent with the defined tools"""
        system_message = """You are a professional ticket creation assistant for Kayako's customer support system.
        Your job is to analyze customer call transcripts and create well-formatted ticket content.
        
        Follow these guidelines:
        1. Use the tools to analyze the conversation
        2. Create a concise but comprehensive summary
        3. Generate a clear subject line that captures the main issue
        4. Determine if the issue was resolved during the call
        5. Format the final ticket content professionally
        
        The conversation will be provided as a list of messages with 'role' and 'content' fields.
        Roles will be either 'assistant' (the AI) or 'caller' (the customer).
        """
        
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_message),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        agent = create_openai_functions_agent(self.llm, self.tools, prompt)
        return AgentExecutor(agent=agent, tools=self.tools, verbose=True)
    
    def summarize_conversation(self, conversation_str: str) -> str:
        """Summarize the key points of a conversation"""
        # Parse the conversation string if needed
        try:
            # Try to extract meaningful content from the string representation
            formatted_messages = []
            for line in conversation_str.split("}, {"):
                if "'role'" in line and "'content'" in line:
                    role_match = re.search(r"'role': '(.*?)'", line)
                    content_match = re.search(r"'content': '(.*?)'", line)
                    if role_match and content_match:
                        role = role_match.group(1)
                        content = content_match.group(1)
                        role_display = "Customer" if role == "caller" else "Support"
                        formatted_messages.append(f"{role_display}: {content}")
            
            conversation_text = "\n".join(formatted_messages)
        except:
            # Fallback to using the raw string
            conversation_text = conversation_str
        
        # Create a prompt for summarization
        summarization_prompt = f"""
        Please summarize the following customer support conversation, focusing on:
        1. The main issue(s) the customer was experiencing
        2. Key information provided by the customer
        3. Solutions or information provided by support
        4. Any follow-up actions discussed
        
        Conversation:
        {conversation_text}
        
        Summary:
        """
        
        # Get the summary from the LLM
        summary_messages = [
            {"role": "system", "content": "You are a helpful assistant that summarizes customer support conversations."},
            {"role": "user", "content": summarization_prompt}
        ]
        
        response = self.llm.invoke(summary_messages)
        return response.content
    
    def create_ticket_subject(self, conversation_str: str) -> str:
        """Create a clear and concise subject line for the ticket"""
        # Parse the conversation string if needed
        try:
            # Try to extract customer messages
            customer_messages = []
            for line in conversation_str.split("}, {"):
                if "'role': 'caller'" in line and "'content'" in line:
                    content_match = re.search(r"'content': '(.*?)'", line)
                    if content_match:
                        customer_messages.append(content_match.group(1))
            
            customer_input = "\n".join(customer_messages)
        except:
            # Fallback to using the raw string
            customer_input = conversation_str
        
        # Create a prompt for subject creation
        subject_prompt = f"""
        Based on the following customer messages, create a clear and concise subject line for a support ticket.
        The subject should be brief (under 75 characters) but descriptive of the main issue.
        
        Customer messages:
        {customer_input}
        
        Subject line:
        """
        
        # Get the subject from the LLM
        subject_messages = [
            {"role": "system", "content": "You are a helpful assistant that creates concise ticket subject lines."},
            {"role": "user", "content": subject_prompt}
        ]
        
        response = self.llm.invoke(subject_messages)
        return response.content
    
    def determine_resolution_status(self, conversation_str: str) -> str:
        """Determine if the issue was resolved during the call"""
        # Parse the conversation string if needed
        try:
            # Try to extract meaningful content
            formatted_messages = []
            for line in conversation_str.split("}, {"):
                if "'role'" in line and "'content'" in line:
                    role_match = re.search(r"'role': '(.*?)'", line)
                    content_match = re.search(r"'content': '(.*?)'", line)
                    if role_match and content_match:
                        role = role_match.group(1)
                        content = content_match.group(1)
                        role_display = "Customer" if role == "caller" else "Support"
                        formatted_messages.append(f"{role_display}: {content}")
            
            conversation_text = "\n".join(formatted_messages)
        except:
            # Fallback to using the raw string
            conversation_text = conversation_str
        
        # Create a prompt for resolution analysis
        resolution_prompt = f"""
        Analyze the following customer support conversation and determine:
        1. Was the customer's issue fully resolved during the call? (Yes/No/Partial)
        2. What specific follow-up actions are needed, if any?
        
        Conversation:
        {conversation_text}
        
        Provide your analysis in a simple format:
        Resolved: [Yes/No/Partial]
        Follow-up Actions: [list actions if any]
        """
        
        # Get the resolution analysis from the LLM
        resolution_messages = [
            {"role": "system", "content": "You are a helpful assistant that analyzes customer support conversations."},
            {"role": "user", "content": resolution_prompt}
        ]
        
        response = self.llm.invoke(resolution_messages)
        return response.content
    
    def process_conversation(self, conversation: List[Dict], caller_number: Optional[str] = None) -> Dict:
        """
        Process the conversation and generate ticket content
        
        Args:
            conversation: A list of message dictionaries
            caller_number: The phone number of the caller (optional)
            
        Returns:
            A dictionary with ticket information
        """
        # Filter out metadata entries and map roles to Langchain expected roles
        filtered_conversation = []
        for msg in conversation:
            if 'metadata' in msg:
                continue
                
            if 'role' in msg and 'content' in msg:
                # Map our roles to Langchain expected roles
                role = msg['role']
                if role == 'caller':
                    role = 'human'  # Map 'caller' to 'human'
                # 'assistant' can stay as is
                
                # Create a new message with the mapped role
                filtered_conversation.append({
                    "role": role,
                    "content": msg['content']
                })
        
        # Convert the conversation to a string for the tools to use
        conversation_str = str(conversation)
        
        # Run the agent
        result = self.agent.invoke({
            "input": f"Process this conversation and create ticket content. Conversation: {conversation_str}",
            "chat_history": filtered_conversation
        })
        
        # Extract the summary, subject, and resolution status from the output
        output = result.get('output', '')
        
        # Extract summary
        summary_match = re.search(r'Summary:(.*?)(?=Subject:|Resolution Status:|$)', output, re.IGNORECASE | re.DOTALL)
        summary = summary_match.group(1).strip() if summary_match else None
        
        # Extract subject
        subject_match = re.search(r'Subject:(.*?)(?=Summary:|Resolution Status:|$)', output, re.IGNORECASE | re.DOTALL)
        subject = subject_match.group(1).strip() if subject_match else None
        
        # Extract resolution status
        resolution_match = re.search(r'Resolution Status:(.*?)(?=Summary:|Subject:|$)', output, re.IGNORECASE | re.DOTALL)
        resolution_status = resolution_match.group(1).strip() if resolution_match else None
        
        # Format the ticket content with better spacing and organization
        ticket_content = []
        
        # Add caller number if available
        if caller_number:
            ticket_content.append(f"Caller: {caller_number}")
            ticket_content.append("")  # Add blank line
            ticket_content.append("")  # Add another blank line
        
        # Add resolution status if available
        if resolution_status:
            ticket_content.append("=== RESOLUTION STATUS ===")
            ticket_content.append("")  # Add blank line
            ticket_content.append(resolution_status)
            ticket_content.append("")  # Add blank line
            ticket_content.append("")  # Add another blank line
            ticket_content.append("")  # Add a third blank line
        
        # Add summary with proper formatting
        if summary:
            ticket_content.append("=== CONVERSATION SUMMARY ===")
            ticket_content.append("")  # Add blank line
            
            # Format the summary with bullet points if it's not already formatted
            if not any(line.strip().startswith('-') or line.strip().startswith('•') for line in summary.split('\n')):
                # Split the summary into paragraphs and format each as a bullet point
                formatted_summary = []
                for paragraph in summary.split('\n\n'):
                    if paragraph.strip():
                        # Further split into sentences for better readability
                        sentences = paragraph.split('. ')
                        for sentence in sentences:
                            if sentence.strip():
                                formatted_summary.append(f"• {sentence.strip()}")
                summary = '\n'.join(formatted_summary)
            
            ticket_content.append(summary)
            ticket_content.append("")  # Add blank line
            ticket_content.append("")  # Add another blank line
            ticket_content.append("")  # Add a third blank line
        
        # Add full transcript with better formatting
        ticket_content.append("=== FULL TRANSCRIPT ===")
        ticket_content.append("")  # Add blank line
        
        # Format the transcript with clear speaker separation
        for msg in conversation:
            if 'metadata' in msg:
                continue
            if 'role' in msg and 'content' in msg:
                role = "Customer" if msg['role'] == 'caller' else "Support"
                ticket_content.append(f"{role}:")
                ticket_content.append("")  # Add blank line after role
                
                # Indent the content for better readability
                content_lines = msg['content'].split('\n')
                for line in content_lines:
                    ticket_content.append(f"    {line}")
                
                ticket_content.append("")  # Add blank line between messages
                ticket_content.append("")  # Add another blank line between messages
        
        # Join all content with proper line breaks
        contents = "\n".join(ticket_content)
        
        # Use the generated subject or a default
        if not subject:
            subject = "Call with AI Assistant"
            
        # Add caller number to subject if available
        if caller_number and caller_number not in subject:
            subject = f"{subject} - Caller: {caller_number}"
        
        return {
            "subject": subject,
            "contents": contents,
            "resolution_status": resolution_status
        } 