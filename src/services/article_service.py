from typing import Dict, List, Optional
import requests
from .auth_service import KayakoAuthService
from models.article import Article

class KayakoArticleService:
    def __init__(self, auth_service: KayakoAuthService):
        self.auth_service = auth_service
        self.base_url = auth_service.base_url
    
    def get_locale_field(self, field_id: int) -> Optional[str]:
        """
        Fetch a locale field by ID
        
        Args:
            field_id (int): The ID of the locale field to fetch
            
        Returns:
            String content of the field or None if not found
        """
        url = f"{self.base_url}/locale/fields/{field_id}.json"
        
        try:
            response = requests.get(
                url,
                headers=self.auth_service.get_auth_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get('data'):
                return None
                
            return data['data'].get('translation')
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
        except Exception as e:
            print(f"Error fetching locale field {field_id}: {e}")
            raise

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
            
            articles = []
            for article_data in data.get('data', []):
                # Get title ID and content ID
                title_id = next((t['id'] for t in article_data.get('titles', []) 
                               if t.get('resource_type') == 'locale_field'), None)
                content_id = next((c['id'] for c in article_data.get('contents', [])
                                 if c.get('resource_type') == 'locale_field'), None)
                
                # Fetch actual title and content
                title = self.get_locale_field(title_id) if title_id else None
                content = self.get_locale_field(content_id) if content_id else None
                
                articles.append(Article.from_api_response(article_data, title, content))
            
            return articles
            
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
            
            article_data = data['data']
            
            # Get title ID and content ID
            title_id = next((t['id'] for t in article_data.get('titles', []) 
                           if t.get('resource_type') == 'locale_field'), None)
            content_id = next((c['id'] for c in article_data.get('contents', [])
                             if c.get('resource_type') == 'locale_field'), None)
            
            # Fetch actual title and content
            title = self.get_locale_field(title_id) if title_id else None
            content = self.get_locale_field(content_id) if content_id else None
            
            return Article.from_api_response(article_data, title, content)
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
        except Exception as e:
            print(f"Error fetching article {article_id}: {e}")
            raise 

    def get_published_articles(self, offset: int = 0, limit: int = 10) -> List[Article]:
        """
        Fetch published articles from Kayako API
        
        Args:
            offset (int): Starting point for pagination
            limit (int): Number of articles to return per page
            
        Returns:
            List of published Article objects
        """
        url = f"{self.base_url}/articles.json"
        
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
            
            articles = []
            for article_data in data.get('data', []):
                # Only process published articles
                if article_data.get('status') == "PUBLISHED":
                    # Get title ID and content ID
                    title_id = next((t['id'] for t in article_data.get('titles', []) 
                                   if t.get('resource_type') == 'locale_field'), None)
                    content_id = next((c['id'] for c in article_data.get('contents', [])
                                     if c.get('resource_type') == 'locale_field'), None)
                    
                    # Fetch actual title and content
                    title = self.get_locale_field(title_id) if title_id else None
                    content = self.get_locale_field(content_id) if content_id else None
                    
                    articles.append(Article.from_api_response(article_data, title, content))
            
            return articles
            
        except Exception as e:
            print(f"Error fetching published articles: {e}")
            raise
    
    def get_all_published_articles(self) -> List[Article]:
        """
        Fetch all published articles by handling pagination automatically
        
        Returns:
            List of all published Article objects
        """
        all_articles = []
        offset = 0
        limit = 100  # Fetch more articles per request
        
        while True:
            articles = self.get_published_articles(offset=offset, limit=limit)
            if not articles:
                break
                
            all_articles.extend(articles)
            
            # Check if we got less than the limit (meaning we're at the end)
            if len(articles) < limit:
                break
                
            offset += limit
            
        return all_articles 