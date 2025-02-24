from typing import List, Dict, Optional, Tuple
from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
import os
from dotenv import load_dotenv
from openai import OpenAI

class KnowledgeBaseSearchService:
    def __init__(self):
        load_dotenv()
        self.embeddings = OpenAIEmbeddings()
        self.pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
        self.index = self.pc.Index(os.getenv('PINECONE_INDEX_NAME'))
        self.client = OpenAI()
    
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
    
    def get_answer(self, query: str, top_k: int = 3) -> Tuple[str, List[Dict]]:
        """
        Search the knowledge base and generate an answer based on the results
        
        Args:
            query (str): The user's question
            top_k (int): Number of chunks to retrieve
            
        Returns:
            Tuple containing:
            - Generated answer (str)
            - List of relevant chunks used (List[Dict])
        """
        # Get relevant chunks
        chunks = self.search(query, top_k=top_k)
        
        if not chunks:
            return "I couldn't find any relevant information to answer your question.", []
        
        # Prepare context from chunks
        context = "\n\n".join([
            f"Article: {chunk['title']}\nContent: {chunk['content']}"
            for chunk in chunks
        ])
        
        # Create prompt for GPT
        system_prompt = """You are a helpful assistant answering questions based on provided knowledge base articles during a phone conversation. 

        IMPORTANT:
        - Only use the provided context to answer the question
        - Keep responses concise and clear, as this is a phone conversation
        - If the context doesn't contain enough information to answer fully, say "I apologize, but I don't have enough information to fully answer your question. I'll have a representative call you back to assist with this."
        - Do not make assumptions or add information beyond what's in the context
        - Include relevant article URLs only if they directly support your answer

        Remember to maintain a helpful and professional tone while keeping responses brief and easy to understand over the phone."""
        
        # Generate response using GPT
        response = self.client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        answer = response.choices[0].message.content
        
        # Add source URLs if they weren't included in the response
        if not any(chunk['url'] for chunk in chunks if chunk['url'] in answer):
            sources = "\n\nSources:"
            for chunk in chunks:
                sources += f"\n- {chunk['url']}"
            answer += sources
        
        return answer, chunks 

    def get_kb_answer(self, query: str) -> str:
        """
        Function specifically formatted for use as a tool call.
        Returns the relevant content found in the knowledge base.
        
        Args:
            query (str): The user's question
            
        Returns:
            str: The relevant content found
        """
        #print(f"\nSearching knowledge base for: {query}")
        
        # Get embeddings and search
        #print("Getting vector embeddings...")
        chunks = self.search(query, top_k=3)
        
        if not chunks:
            print("No relevant chunks found")
            return "No relevant information found."
        
        #print(f"Found {len(chunks)} relevant chunks")
        
        # Format the content with sources
        content = []
        for i, chunk in enumerate(chunks, 1):
            #print(f"Processing chunk {i} from article '{chunk['title']}'")
            content.append(
                f"From article '{chunk['title']}':\n"
                f"{chunk['content']}\n"
                f"Source: {chunk['url']}"
            )
        
        final_content = "\n\n".join(content)
        #print("Finished processing knowledge base response")
        return final_content 