from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseAgent(ABC):
    def __init__(self, name: str):
        self.name = name
        self.state: Dict[str, Any] = {}
    
    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process the input data and return a response"""
        pass
    
    def update_state(self, new_state: Dict[str, Any]) -> None:
        """Update the agent's state"""
        self.state.update(new_state)
    
    def get_state(self) -> Dict[str, Any]:
        """Get the current state of the agent"""
        return self.state.copy()
    
    def clear_state(self) -> None:
        """Clear the agent's state"""
        self.state.clear() 