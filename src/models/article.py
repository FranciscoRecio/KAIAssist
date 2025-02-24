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
    def from_api_response(cls, data: dict) -> 'Article':
        """Create an Article instance from Kayako API response data"""
        # Extract the English title if available
        title = None
        for title_obj in data.get('titles', []):
            if isinstance(title_obj, dict) and title_obj.get('locale') == 'en-us':
                title = title_obj.get('translation')
                break
        
        # Extract the English content if available
        content = None
        for content_obj in data.get('contents', []):
            if isinstance(content_obj, dict) and content_obj.get('locale') == 'en-us':
                content = content_obj.get('translation')
                break
        
        return cls(
            id=data['id'],
            status=data['status'],
            helpcenter_url=data['helpcenter_url'],
            title=title,
            content=content
        ) 