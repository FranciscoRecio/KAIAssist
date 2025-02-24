import os
import sys
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent.parent / 'src'
sys.path.append(str(src_path))

from services.search_service import KnowledgeBaseSearchService

def main():
    try:
        search_service = KnowledgeBaseSearchService()
        
        # Get search query from command line argument or use default
        query = sys.argv[1] if len(sys.argv) > 1 else "How do I locate an administrator's profile in AdvocateHub?"
        
        print(f"\nSearching for: {query}")
        results = search_service.search(query)
        
        print("\nSearch Results:")
        for i, result in enumerate(results, 1):
            print(f"\n--- Result {i} (Score: {result['score']:.3f}) ---")
            print(f"Title: {result['title']}")
            print(f"URL: {result['url']}")
            print(f"Article ID: {result['article_id']}")
            print(f"Chunk Index: {result['chunk_index']}")
            print("\nContent Preview:")
            print(result['content'][:300] + "..." if len(result['content']) > 300 else result['content'])
            print("-" * 50)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 