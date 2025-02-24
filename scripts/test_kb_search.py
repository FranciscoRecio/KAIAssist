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
        answer, chunks = search_service.get_answer(query)
        
        print("\nAnswer:")
        print(answer)
        
        print("\nRelevant Chunks Used:")
        for i, chunk in enumerate(chunks, 1):
            print(f"\n--- Chunk {i} (Score: {chunk['score']:.3f}) ---")
            print(f"Title: {chunk['title']}")
            print(f"URL: {chunk['url']}")
            print(f"Article ID: {chunk['article_id']}")
            print(f"Chunk Index: {chunk['chunk_index']}")
            print("-" * 50)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 