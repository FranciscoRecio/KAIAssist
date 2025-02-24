from typing import Dict, List, Optional
import requests
from .auth_service import KayakoAuthService
from models.article import Article

class KayakoArticleService:
    def __init__(self, auth_service: KayakoAuthService):
        self.auth_service = auth_service
        self.base_url = auth_service.base_url
    
    def get_articles(self, offset: int = 0, limit: int = 10) -> List[Article]:
        """
        Fetch articles from Kayako API
        
        Args:
            offset (int): Starting point for pagination
            limit (int): Number of articles to return per page
            
        Returns:
            List of Article objects
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
            data = response.json()
            
            return [Article.from_api_response(article_data) 
                   for article_data in data.get('data', [])]
            
        except Exception as e:
            print(f"Error fetching articles: {e}")
            raise
    
    def get_all_articles(self) -> List[Article]:
        """
        Fetch all articles by handling pagination automatically
        
        Returns:
            List of all Article objects
        """
        all_articles = []
        offset = 0
        limit = 100  # Fetch more articles per request
        
        while True:
            articles = self.get_articles(offset=offset, limit=limit)
            if not articles:
                break
                
            all_articles.extend(articles)
            
            # Check if we got less than the limit (meaning we're at the end)
            if len(articles) < limit:
                break
                
            offset += limit
            
        return all_articles
    
    def get_article(self, article_id: int) -> Optional[Article]:
        """
        Fetch a specific article by ID
        
        Args:
            article_id (int): The ID of the article to fetch
            
        Returns:
            Article object or None if not found
        """
        url = f"{self.base_url}/articles/{article_id}.json"
        
        try:
            response = requests.get(
                url,
                headers=self.auth_service.get_auth_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get('data'):
                return None
                
            return Article.from_api_response(data['data'])
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
        except Exception as e:
            print(f"Error fetching article {article_id}: {e}")
            raise 