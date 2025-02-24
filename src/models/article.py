from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from bs4 import BeautifulSoup

@dataclass
class Article:
    id: int
    status: str
    helpcenter_url: str
    updated_at: str
    title: Optional[str] = None
    content: Optional[str] = None
    
    @staticmethod
    def _clean_html(html_content: Optional[str]) -> Optional[str]:
        """Remove HTML tags and clean up whitespace"""
        if not html_content:
            return None
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text(separator=' ')
        # Clean up whitespace
        return ' '.join(text.split())
    
    @classmethod
    def from_api_response(cls, data: dict, title: Optional[str] = None, content: Optional[str] = None) -> 'Article':
        """Create an Article instance from Kayako API response data"""
        return cls(
            id=data['id'],
            status=data['status'],
            helpcenter_url=data['helpcenter_url'],
            updated_at=data['updated_at'],
            title=cls._clean_html(title),
            content=cls._clean_html(content)
        ) 