from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Article:
    id: int
    status: str
    helpcenter_url: str
    title: Optional[str] = None
    content: Optional[str] = None
    
    @classmethod
    def from_api_response(cls, data: dict, title: Optional[str] = None, content: Optional[str] = None) -> 'Article':
        """Create an Article instance from Kayako API response data"""
        return cls(
            id=data['id'],
            status=data['status'],
            helpcenter_url=data['helpcenter_url'],
            title=title,
            content=content
        ) 