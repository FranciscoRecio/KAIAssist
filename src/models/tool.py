from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class ToolParameter:
    type: str
    description: str
    enum: List[str] = None

@dataclass
class ToolProperties:
    type: str = "object"
    properties: Dict[str, ToolParameter] = None
    required: List[str] = None

@dataclass
class Tool:
    type: str
    name: str
    description: str
    parameters: ToolProperties

class Tools:
    @staticmethod
    def search_knowledge_base() -> Dict[str, Any]:
        return {
            "type": "function",
            "name": "search_knowledge_base",
            "description": "Search the knowledge base for information to answer user questions",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user's question to search for in the knowledge base"
                    }
                },
                "required": ["query"]
            }
        }

    @staticmethod
    def end_call() -> Dict[str, Any]:
        return {
            "type": "function",
            "name": "end_call",
            "description": "End the current call",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for ending the call",
                        "enum": ["question_answered", "insufficient_information"]
                    }
                },
                "required": ["reason"]
            }
        }

    @staticmethod
    def get_agent_response() -> Dict[str, Any]:
        return {
            "type": "function",
            "name": "get_agent_response",
            "description": "Get a response from the AI agent for any user query",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user's query or message to process through the AI agent"
                    }
                },
                "required": ["query"]
            }
        }

    @staticmethod
    def get_all_tools() -> List[Dict[str, Any]]:
        return [
            Tools.get_agent_response()
        ] 