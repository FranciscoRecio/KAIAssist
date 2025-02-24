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
        
        print("Fetching 5 articles...")
        articles = article_service.get_articles(limit=5)
        
        print(f"\nFound {len(articles)} articles:")
        for article in articles:
            print(f"\nID: {article.id}")
            print(f"Title: {article.title or 'Untitled'}")
            print(f"Status: {article.status}")
            print(f"URL: {article.helpcenter_url}")
            print(f"Content: {'Present' if article.content else 'Empty'}")
            if article.content:
                print("\nContent Preview:")
                print(article.content[:500] + "..." if len(article.content) > 500 else article.content)
            print("-" * 50)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 