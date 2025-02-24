from typing import Dict, List, Optional
import requests
from .auth_service import KayakoAuthService

class KayakoArticleService:
    def __init__(self, auth_service: KayakoAuthService):
        self.auth_service = auth_service
        self.base_url = auth_service.base_url
    
    def get_articles(self, offset: int = 0, limit: int = 10) -> Dict:
        """
        Fetch articles from Kayako API
        
        Args:
            offset (int): Starting point for pagination
            limit (int): Number of articles to return per page
            
        Returns:
            Dict containing article data and pagination info
        """
        url = f"{self.base_url}/articles.json"
        
        # Add pagination parameters
        params = {
            'offset': offset,
            'limit': limit
        }
        
        try:
            response = requests.get(
                url,
                params=params,
                headers=self.auth_service.get_auth_headers()
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            print(f"Error fetching articles: {e}")
            raise
    
    def get_all_articles(self) -> List[Dict]:
        """
        Fetch all articles by handling pagination automatically
        
        Returns:
            List of all articles
        """
        all_articles = []
        offset = 0
        limit = 100  # Fetch more articles per request
        
        while True:
            response = self.get_articles(offset=offset, limit=limit)
            
            if not response.get('data'):
                break
                
            all_articles.extend(response['data'])
            
            # Check if there are more articles
            if not response.get('next_url'):
                break
                
            offset += limit
            
        return all_articles
    
    def get_article(self, article_id: int) -> Optional[Dict]:
        """
        Fetch a specific article by ID
        
        Args:
            article_id (int): The ID of the article to fetch
            
        Returns:
            Dict containing article data or None if not found
        """
        url = f"{self.base_url}/articles/{article_id}.json"
        
        try:
            response = requests.get(
                url,
                headers=self.auth_service.get_auth_headers()
            )
            response.raise_for_status()
            return response.json().get('data')
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
        except Exception as e:
            print(f"Error fetching article {article_id}: {e}")
            raise 