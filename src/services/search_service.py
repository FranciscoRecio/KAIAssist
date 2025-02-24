from typing import List, Dict, Optional
from pinecone import Pinecone
from langchain_community.embeddings import OpenAIEmbeddings
import os
from dotenv import load_dotenv

class KnowledgeBaseSearchService:
    def __init__(self):
        load_dotenv()
        self.embeddings = OpenAIEmbeddings()
        self.pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
        self.index = self.pc.Index(os.getenv('PINECONE_INDEX_NAME'))
    
    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        Search the knowledge base for content similar to the query
        
        Args:
            query (str): The search query
            top_k (int): Number of results to return
            
        Returns:
            List of dictionaries containing matched content and metadata
        """
        # Generate embedding for the query
        query_embedding = self.embeddings.embed_query(query)
        
        # Search Pinecone
        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True
        )
        
        # Format results
        formatted_results = []
        for match in results.matches:
            formatted_results.append({
                'score': match.score,
                'article_id': int(match.metadata['article_id']),
                'title': match.metadata['title'],
                'url': match.metadata['url'],
                'chunk_index': int(match.metadata['chunk_index']),
                'content': match.metadata.get('content', 'No content available')
            })
        
        return formatted_results 