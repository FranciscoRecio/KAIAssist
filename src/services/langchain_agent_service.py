import os
import json
import asyncio
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from fastapi import WebSocket
from dotenv import load_dotenv

from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.agents import Tool, AgentExecutor, create_react_agent
from langchain.tools import BaseTool

# Import tools and input classes from langchain_tools.py
from .langchain_tools import (
    SearchKnowledgeBaseTool,
    EndCallTool,
    SendInstructionTool,
    SendInterimMessageTool,
    HandleInterruptionTool,
    InitiateGreetingTool,
    # Also import the input classes
    SearchKnowledgeInput,
    EndCallInput,
    SendInstructionInput
)

class CallState:
    INITIAL = "initial"
    SEARCHING_KB = "searching_kb"
    ANSWERING = "answering"
    CONFIRMING = "awaiting_answer_feedback"
    FOLLOW_UP = "awaiting_more_questions"
    ENDING = "ending"
    ENDING_QUESTION_ANSWERED = "ending_question_answered"
    ENDING_INSUFFICIENT_INFO = "ending_insufficient_info"

class LangChainAgentService:
    def __init__(self):
        load_dotenv()
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.2,
            api_key=os.getenv('OPENAI_API_KEY')
        )
        self.memory = ConversationBufferMemory(return_messages=True)
        self.agent_executor = None  # Will be initialized per call
        self.tools = []  # Will be populated during initialization for call
        self.current_state = CallState.INITIAL  # Track the current conversation state
        
    async def initialize_for_call(self, 
                                websocket: WebSocket,
                                openai_ws: WebSocket,
                                stream_sid: str,
                                conversation_service,
                                knowledge_service):
        """Initialize the agent for a new call"""
        print("Initializing LangChain agent for call")
        
        # Initialize memory
        self.memory = ConversationBufferMemory(return_messages=True)
        
        # Initialize tools
        tools = [
            SearchKnowledgeBaseTool(knowledge_service, openai_ws),
            SendInstructionTool(openai_ws),
            EndCallTool(websocket, openai_ws, stream_sid, conversation_service)
        ]
        
        # Create the agent prompt with our custom instructions
        from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate
        
        # Our custom system prompt with conversation flow rules
        custom_system_prompt = """You are a professional AI phone assistant managing a customer service call.

        CRITICAL CONVERSATION RULES - YOU MUST FOLLOW THESE EXACTLY:

        1. INITIAL RESPONSE:
           - ALWAYS use search_knowledge_base tool first for any question
           - After receiving knowledge, use send_instruction tool to provide the information and ALWAYS end with "Did that answer your question?"
           - Wait for caller's response

        2. AFTER CALLER RESPONDS TO "Did that answer your question?":
           IF CALLER SAYS NO:
           - Use send_instruction tool to say "I apologize, but I don't have enough information to fully answer your question. I'll have a representative call you back to assist with this. Thank you for calling."
           - Use end_call tool with reason "insufficient_information"
           - End conversation

           IF CALLER SAYS YES:
           - Use send_instruction tool to ask "Do you have any other questions I can help you with?"
           - Wait for caller's response

        3. AFTER CALLER RESPONDS TO "Do you have any other questions?":
           IF CALLER SAYS NO:
           - Use send_instruction tool to say "Thank you for calling. Have a great day!"
           - Use end_call tool with reason "question_answered"
           - End conversation

           IF CALLER SAYS YES:
           - Start over from step 1 with their new question

        Current conversation state: {current_state}

        You have access to the following tools:

        {tools}

        To use a tool, please use the following format:
        ```
        Action: the action to take, should be one of [{tool_names}]
        Action Input: the input to the action
        Observation: the result of the action
        ```

        When you have a response for the human, or if you want to send a message to the caller, you MUST use the send_instruction tool.
        
        Begin!
        """
        
        # Create the prompt template with all required variables
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(custom_system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # Create the agent
        agent = create_react_agent(
            llm=self.llm,
            tools=tools,
            prompt=prompt
        )
        
        # Create the agent executor
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True,
            return_intermediate_steps=True,
            output_keys=["output"]
        )
        
        # Initialize state
        self.current_state = "initial"
        
        print("LangChain agent initialized successfully")
    
    async def process_user_input(self, user_input):
        """Process user input through the agent"""
        try:
            print(f"Processing user input: {user_input}")
            
            # Format the input for the agent
            if isinstance(user_input, dict) and "query" in user_input:
                query = user_input["query"]
            else:
                query = user_input
            
            # Import the necessary message types
            from langchain_core.messages import AIMessage, HumanMessage
            
            # Create empty agent_scratchpad as a list of base messages
            agent_scratchpad = []
            
            # Get chat history from memory
            chat_history = self.memory.chat_memory.messages if hasattr(self.memory, 'chat_memory') else []
            
            # Run the agent with all required variables
            result = await self.agent_executor.ainvoke(
                {
                    "input": query,
                    "current_state": self.current_state,
                    "chat_history": chat_history,
                    "agent_scratchpad": agent_scratchpad
                }
            )
            
            print(f"Agent result: {result}")
            
            # Extract the final output and intermediate steps
            output = result.get("output", "")
            steps = result.get("intermediate_steps", [])
            
            # Determine the new state based on the agent's actions
            new_state = self._determine_new_state(steps)
            
            return {
                "success": True,
                "response": output,
                "current_state": new_state
            }
        except Exception as e:
            print(f"Error in agent execution: {e}")
            import traceback
            print(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "current_state": self.current_state
            }
        
    def _determine_new_state(self, steps):
        """Determine the new state based on the agent's actions"""
        # Default to keeping the current state
        new_state = self.current_state
        
        # Look for state-changing actions in the steps
        for action, observation in steps:
            tool = action.tool
            tool_input = action.tool_input
            
            # State transitions based on tools used
            if tool == "search_knowledge_base":
                # When knowledge is searched, we're waiting for the user's feedback
                new_state = "awaiting_answer_feedback"
                
            elif tool == "send_instruction":
                # Check the content of the instruction to determine state
                instruction = str(tool_input)
                
                if "Did that answer your question?" in instruction:
                    new_state = "awaiting_answer_feedback"
                    
                elif "Do you have any other questions" in instruction:
                    new_state = "awaiting_further_questions"
                    
                elif "I apologize, but I don't have enough information" in instruction:
                    new_state = "preparing_to_end_insufficient_info"
                    
                elif "Thank you for calling" in instruction and new_state != "preparing_to_end_insufficient_info":
                    new_state = "preparing_to_end_question_answered"
                    
            elif tool == "end_call":
                # Check the reason for ending the call
                reason = str(tool_input).get("reason", "") if isinstance(tool_input, dict) else str(tool_input)
                
                if "insufficient_information" in reason:
                    new_state = "call_ended_insufficient_info"
                elif "question_answered" in reason:
                    new_state = "call_ended_question_answered"
                else:
                    new_state = "call_ended"
        
        print(f"State transition: {self.current_state} -> {new_state}")
        
        # Update the current state
        self.current_state = new_state
        
        return new_state