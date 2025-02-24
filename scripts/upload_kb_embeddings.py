import os
import sys
from pathlib import Path
from typing import List, Dict, Set
from pinecone import Pinecone
from langchain_community.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Pinecone as LangchainPinecone
from dotenv import load_dotenv

# Add the src directory to Python path
src_path = Path(__file__).parent.parent / 'src'
sys.path.append(str(src_path))

from services.auth_service import KayakoAuthService
from services.article_service import KayakoArticleService

def prepare_article_chunks(articles: List[Dict]) -> List[Dict]:
    """
    Split articles into chunks and prepare them for embedding
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    
    chunks = []
    for article in articles:
        if not article.content:
            continue
            
        # Create a combined text that includes both title and content
        full_text = f"Title: {article.title}\n\nContent: {article.content}"
        
        # Split the text into chunks
        texts = text_splitter.split_text(full_text)
        
        # Create metadata for each chunk
        for i, text in enumerate(texts):
            # Create a deterministic ID based on article ID and chunk index
            chunk_id = f"article_{article.id}_chunk_{i}"
            
            chunks.append({
                "id": chunk_id,  # Use consistent IDs
                "text": text,
                "metadata": {
                    "article_id": article.id,
                    "title": article.title,
                    "url": article.helpcenter_url,
                    "chunk_index": i,
                    "updated_at": article.updated_at,  # Add last update timestamp
                    "content": text  # Add the content to metadata
                }
            })
    
    return chunks

def get_existing_article_ids(index) -> Set[int]:
    """
    Get all article IDs that currently exist in the index
    """
    # Query with empty vector to get metadata
    results = index.query(
        vector=[0] * 1536,  # OpenAI embedding dimension
        top_k=10000,  # Adjust based on your total vectors
        include_metadata=True
    )
    
    article_ids = set()
    for match in results.matches:
        if match.metadata and 'article_id' in match.metadata:
            article_ids.add(int(match.metadata['article_id']))  # Ensure integer type
    
    return article_ids

def delete_article_chunks(index, article_id: int):
    """
    Delete all chunks for a specific article
    """
    # Ensure article_id is an integer
    article_id = int(article_id)
    
    # Get all vector IDs for this article (they start with article_{id}_chunk)
    prefix = f"article_{article_id}_chunk"
    vector_ids = []
    
    # List all vectors with our prefix
    for ids in index.list(prefix=prefix):
        vector_ids.extend(ids)
    
    if vector_ids:
        # Delete the vectors by their IDs
        index.delete(ids=vector_ids)
        print(f"Deleted {len(vector_ids)} chunks for article {article_id}")
    else:
        print(f"No chunks found for article {article_id}")

def get_article_metadata(index, article_id: int) -> Dict:
    """
    Get metadata for an article's chunks from Pinecone
    Returns None if article doesn't exist
    """
    results = index.query(
        vector=[0] * 1536,  # OpenAI embedding dimension
        filter={"article_id": article_id},
        top_k=1,
        include_metadata=True
    )
    
    if results.matches:
        return results.matches[0].metadata
    return None

def needs_update(index, article) -> bool:
    """
    Check if an article needs to be updated in the index
    """
    existing_metadata = get_article_metadata(index, article.id)
    if not existing_metadata:
        print(f"Article {article.id} is new")
        return True
        
    existing_updated_at = existing_metadata.get('updated_at')
    if existing_updated_at != article.updated_at:
        print(f"Article {article.id} has been updated (old: {existing_updated_at}, new: {article.updated_at})")
        return True
        
    print(f"Article {article.id} is unchanged")
    return False

def main():
    try:
        # Load environment variables
        load_dotenv()
        
        # Initialize Kayako services
        auth_service = KayakoAuthService()
        article_service = KayakoArticleService(auth_service)
        
        # Initialize OpenAI embeddings
        embeddings = OpenAIEmbeddings()
        
        # Initialize Pinecone
        pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
        
        index_name = os.getenv('PINECONE_INDEX_NAME')
        index = pc.Index(index_name)
        
        print("Fetching published articles...")
        articles = article_service.get_all_published_articles()  # Get just one article
        print(f"Found {len(articles)} published articles")
        
        # Get current article IDs from Pinecone
        print("Checking existing articles in Pinecone...")
        existing_article_ids = get_existing_article_ids(index)
        
        # Get new article IDs
        new_article_ids = {int(article.id) for article in articles}  # Ensure integer type
        
        # Find articles to delete
        articles_to_delete = existing_article_ids - new_article_ids
        if articles_to_delete:
            print(f"Deleting {len(articles_to_delete)} removed articles...")
            for article_id in articles_to_delete:
                delete_article_chunks(index, article_id)
        
        # Filter articles that need updating
        articles_to_update = [article for article in articles if needs_update(index, article)]
        
        if not articles_to_update:
            print("No articles need updating")
            return
            
        print("Preparing article chunks...")
        chunks = prepare_article_chunks(articles_to_update)
        print(f"Created {len(chunks)} chunks")
        
        if chunks:
            print("Upserting vectors to Pinecone...")
            # Generate embeddings
            texts = [chunk["text"] for chunk in chunks]
            vectors = embeddings.embed_documents(texts)
            
            # Prepare vectors for upsert
            to_upsert = []
            for i, vector in enumerate(vectors):
                to_upsert.append({
                    "id": chunks[i]["id"],
                    "values": vector,
                    "metadata": chunks[i]["metadata"]
                })
            
            # Upsert in batches of 100
            batch_size = 100
            for i in range(0, len(to_upsert), batch_size):
                batch = to_upsert[i:i + batch_size]
                index.upsert(vectors=batch)
                print(f"Upserted batch {i//batch_size + 1} of {(len(to_upsert) + batch_size - 1)//batch_size}")
            
            print("Successfully uploaded embeddings to Pinecone!")
        
        print("\nSummary:")
        print(f"Total articles processed: {len(articles)}")
        print(f"Articles updated: {len(articles_to_update)}")
        print(f"New chunks created: {len(chunks)}")
        print(f"Articles deleted: {len(articles_to_delete)}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 