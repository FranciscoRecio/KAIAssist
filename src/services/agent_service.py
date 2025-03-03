import json
import os
from typing import Dict, List, Any
from fastapi import WebSocket
from openai import OpenAI
from dotenv import load_dotenv

class AgentRole:
    MANAGER = "manager"
    KNOWLEDGE = "knowledge_specialist"
    CONVERSATION = "conversation_specialist"
    CALL_CONTROL = "call_control_specialist"

class AgentService:
    def __init__(self):
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.agents = self._initialize_agents()
        self.conversation_history = []
        
    def _initialize_agents(self) -> Dict[str, Dict[str, str]]:
        """Initialize the agent system with roles and instructions"""
        return {
            AgentRole.MANAGER: {
                "name": "Manager",
                "instructions": """You are the manager agent overseeing a phone conversation.
                Your job is to:
                1. Determine which specialist agent should handle each user query
                2. Ensure the conversation follows the required structure
                3. Make high-level decisions about when to end the call
                
                Always maintain this conversation flow:
                1. Search knowledge base for answers
                2. Ask if the answer was helpful
                3. If yes, ask if they have more questions
                4. If no, apologize and end the call
                """
            },
            AgentRole.KNOWLEDGE: {
                "name": "Knowledge Specialist",
                "instructions": """You are the knowledge specialist.
                Your job is to search the knowledge base and provide accurate information.
                Always format your responses clearly and concisely.
                """
            },
            AgentRole.CONVERSATION: {
                "name": "Conversation Specialist",
                "instructions": """You are the conversation specialist.
                Your job is to maintain a natural, friendly conversation flow.
                Ensure transitions between topics are smooth and professional.
                """
            },
            AgentRole.CALL_CONTROL: {
                "name": "Call Control Specialist",
                "instructions": """You are the call control specialist.
                Your job is to manage the technical aspects of the call:
                1. Handle interruptions
                2. Execute the end call procedure
                3. Ensure all conversation data is properly saved
                """
            }
        }
    
    async def process_user_input(self, 
                               user_input: str, 
                               current_state: str,
                               websocket: WebSocket,
                               openai_ws: WebSocket,
                               stream_sid: str) -> str:
        """Process user input through the agent hierarchy"""
        # Add user input to conversation history
        self.conversation_history.append({"role": "user", "content": user_input})
        
        # First, consult the manager agent to decide what to do
        manager_decision = await self._consult_manager(user_input, current_state)
        
        # Based on manager's decision, route to appropriate specialist
        if manager_decision["next_action"] == "search_knowledge":
            # Route to knowledge specialist
            knowledge_response = await self._consult_specialist(
                AgentRole.KNOWLEDGE, 
                user_input, 
                manager_decision["instructions"]
            )
            
            # Execute knowledge search
            search_args = json.dumps({"query": user_input})
            await self._execute_tool_call("search_knowledge_base", search_args, openai_ws)
            
            # Update state
            return "initial_response"
            
        elif manager_decision["next_action"] == "end_call":
            # Route to call control specialist
            call_control_response = await self._consult_specialist(
                AgentRole.CALL_CONTROL,
                user_input,
                manager_decision["instructions"]
            )
            
            # Execute end call
            reason = "question_answered" if manager_decision.get("reason") == "satisfied" else "insufficient_information"
            end_args = json.dumps({"reason": reason})
            await self._execute_tool_call("end_call", end_args, websocket, openai_ws, stream_sid)
            
            # Update state
            return "ending"
            
        elif manager_decision["next_action"] == "continue_conversation":
            # Route to conversation specialist
            conversation_response = await self._consult_specialist(
                AgentRole.CONVERSATION,
                user_input,
                manager_decision["instructions"]
            )
            
            # Send instruction to guide the model
            await self._send_instruction(openai_ws, conversation_response["response"])
            
            # Update state
            return manager_decision["next_state"]
        
        # Default return
        return current_state
    
    async def _consult_manager(self, user_input: str, current_state: str) -> Dict[str, Any]:
        """Consult the manager agent to decide what to do next"""
        prompt = f"""
        Current state: {current_state}
        User input: "{user_input}"
        
        Based on this information and the conversation history, what should we do next?
        
        Options:
        1. search_knowledge - Search the knowledge base for information
        2. continue_conversation - Continue the conversation with specific instructions
        3. end_call - End the call with a specific reason
        
        Respond in JSON format:
        {{
            "next_action": "search_knowledge|continue_conversation|end_call",
            "next_state": "state_name",
            "instructions": "Instructions for the specialist agent",
            "reason": "satisfied|insufficient_information" (only for end_call)
        }}
        """
        
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": self.agents[AgentRole.MANAGER]["instructions"]},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
    
    async def _consult_specialist(self, role: str, user_input: str, instructions: str) -> Dict[str, Any]:
        """Consult a specialist agent for specific tasks"""
        prompt = f"""
        User input: "{user_input}"
        Instructions from manager: {instructions}
        
        How should we respond to this?
        
        Respond in JSON format:
        {{
            "response": "Your detailed response or instructions",
            "additional_info": "Any additional information or context"
        }}
        """
        
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": self.agents[role]["instructions"]},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
    
    async def _execute_tool_call(self, 
                               function_name: str, 
                               function_args: str, 
                               websocket: WebSocket = None,
                               openai_ws: WebSocket = None,
                               stream_sid: str = None) -> None:
        """Execute a tool call based on agent decisions"""
        # This would call your existing tool service methods
        pass
    
    async def _send_instruction(self, openai_ws: WebSocket, instruction: str) -> None:
        """Send an instruction to guide the model's response"""
        instruction_message = {
            "type": "response.create",
            "response": {
                "instructions": instruction
            }
        }
        await openai_ws.send(json.dumps(instruction_message)) 