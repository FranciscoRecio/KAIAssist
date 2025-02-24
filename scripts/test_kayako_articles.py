import os
import sys
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent.parent / 'src'
sys.path.append(str(src_path))

from services.auth_service import KayakoAuthService
from services.article_service import KayakoArticleService

def main():
    try:
        # Initialize services
        auth_service = KayakoAuthService()
        article_service = KayakoArticleService(auth_service)
        
        print("Fetching all articles...")
        articles = article_service.get_all_articles()
        
        print(f"\nFound {len(articles)} articles:")
        for article in articles:
            # Extract the English title if available
            title = "Untitled"
            for title_obj in article.get('titles', []):
                if isinstance(title_obj, dict) and title_obj.get('locale') == 'en-us':
                    title = title_obj.get('translation', 'Untitled')
                    break
            
            print(f"\nID: {article['id']}")
            print(f"Title: {title}")
            print(f"Status: {article['status']}")
            print(f"Created: {article['created_at']}")
            print(f"URL: {article['helpcenter_url']}")
            print("-" * 50)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 