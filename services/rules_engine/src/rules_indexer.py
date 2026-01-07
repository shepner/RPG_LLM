"""Rules content indexer for semantic search."""

import os
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
import chromadb
from chromadb.config import Settings

from shared.embedding_provider import GeminiEmbeddingProvider


class RulesIndexer:
    """Indexes rules content for semantic search and LLM retrieval."""
    
    def __init__(self, chroma_db_path: str, rules_dir: Path):
        """Initialize indexer."""
        self.chroma_db_path = chroma_db_path
        self.rules_dir = rules_dir
        
        # Initialize ChromaDB
        os.makedirs(chroma_db_path, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(
            path=chroma_db_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Initialize embedding provider first
        try:
            # Ensure GOOGLE_APPLICATION_CREDENTIALS is set correctly
            creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if creds_path and not os.path.exists(creds_path):
                # Try to find it in the container path
                container_path = "/app/credentials.json"
                if os.path.exists(container_path):
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = container_path
                    print(f"Using credentials from container path: {container_path}")
                else:
                    print(f"Warning: Credentials file not found at {creds_path} or {container_path}")
            self.embedding_provider = GeminiEmbeddingProvider()
        except Exception as e:
            error_msg = str(e)
            # Clean up error message to not expose host paths
            if "/Users/" in error_msg:
                error_msg = error_msg.replace("/Users/shepner/", "/app/")
            print(f"Warning: Embedding provider not available: {error_msg}")
            self.embedding_provider = None
        
        # Get or create collection with embedding function if available
        if self.embedding_provider:
            try:
                from shared.vector_store.chroma_manager import ChromaManager
                self.chroma_manager = ChromaManager(
                    collection_name="rules_content",
                    persist_directory=chroma_db_path,
                    embedding_function=self.embedding_provider.get_embedding_function()
                )
                self.collection = self.chroma_manager.collection
            except Exception as e:
                print(f"Warning: Failed to initialize ChromaManager with embeddings: {e}")
                # Fallback to basic collection
                self.collection = self.chroma_client.get_or_create_collection(
                    name="rules_content",
                    metadata={"description": "Indexed rules content for semantic search"}
                )
                self.chroma_manager = None
        else:
            # No embedding provider, use basic collection
            self.collection = self.chroma_client.get_or_create_collection(
                name="rules_content",
                metadata={"description": "Indexed rules content for semantic search"}
            )
            self.chroma_manager = None
    
    async def index_file(
        self, 
        file_id: str, 
        filename: str, 
        content: str, 
        metadata: Dict[str, Any],
        progress_callback: Optional[callable] = None
    ) -> None:
        """
        Index a rules file's content for semantic search.
        
        Args:
            file_id: Unique file identifier
            filename: Original filename
            content: Extracted text content
            metadata: Additional metadata (file type, category, etc.)
            progress_callback: Optional callback function(current, total) for progress updates
        """
        if not content or len(content.strip()) == 0:
            return
        
        if not self.embedding_provider:
            print("Warning: Embedding provider not available, skipping indexing")
            return
        
        # Chunk content for better retrieval (split by paragraphs or sections)
        if progress_callback:
            progress_callback(0, 100, "chunking")
        
        chunks = self._chunk_content(content, chunk_size=1000, overlap=200)
        total_chunks = len(chunks)
        
        # Report progress: chunking complete (10% of total work)
        if progress_callback:
            progress_callback(10, 100, "chunking")
        
        # Generate embeddings and store
        try:
            # Report progress: generating embeddings (10-60% of total work)
            if progress_callback:
                progress_callback(10, 100, "generating_embeddings")
            
            # Generate embeddings for all chunks at once
            # This is the longest step, so we'll update progress incrementally if possible
            embeddings_response = await self.embedding_provider.generate(chunks)
            embeddings = embeddings_response.embeddings
            
            # Report progress: embeddings generated (60% of total work)
            if progress_callback:
                progress_callback(60, 100, "preparing_data")
            
            # Prepare data for batch insert
            chunk_ids = []
            chunk_metadatas = []
            for i, chunk in enumerate(chunks):
                chunk_id = f"{file_id}_chunk_{i}"
                chunk_ids.append(chunk_id)
                chunk_metadatas.append({
                    **metadata,
                    "chunk_index": i,
                    "total_chunks": total_chunks,
                    "filename": filename
                })
            
            # Report progress: data prepared, now storing (80% of total work)
            if progress_callback:
                progress_callback(80, 100, "storing")
            
            # Add to ChromaDB collection
            self.collection.add(
                ids=chunk_ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=chunk_metadatas
            )
            
            # Report progress: complete (100%)
            if progress_callback:
                progress_callback(100, 100, "complete")
        except Exception as e:
            print(f"Warning: Failed to index file {filename}: {e}")
            if progress_callback:
                progress_callback(0, 100, "error")
            raise
    
    def _chunk_content(self, content: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split content into overlapping chunks, respecting paragraph breaks."""
        chunks = []
        
        # First, split by paragraphs (double newlines, or single newline followed by whitespace)
        paragraphs = []
        for para in content.split('\n\n'):
            para = para.strip()
            if para:
                paragraphs.append(para)
        
        # If no paragraph breaks found, try single newlines
        if len(paragraphs) == 1:
            paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        
        # If still no breaks, split by sentences (period, exclamation, question mark)
        if len(paragraphs) == 1:
            import re
            sentences = re.split(r'([.!?]\s+)', paragraphs[0])
            paragraphs = []
            current_sentence = ""
            for part in sentences:
                current_sentence += part
                if part.strip() and part.strip()[-1] in '.!?':
                    paragraphs.append(current_sentence.strip())
                    current_sentence = ""
            if current_sentence.strip():
                paragraphs.append(current_sentence.strip())
        
        # Now chunk paragraphs, respecting chunk_size
        current_chunk = []
        current_length = 0
        
        for para in paragraphs:
            para_length = len(para) + 2  # +2 for paragraph separator
            
            # If adding this paragraph would exceed chunk_size, save current chunk
            if current_length + para_length > chunk_size and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                
                # Start new chunk with overlap (last paragraph or part of it)
                if len(current_chunk) > 0:
                    # Use last paragraph as overlap if it's not too long
                    last_para = current_chunk[-1]
                    if len(last_para) <= chunk_size // 2:
                        current_chunk = [last_para]
                        current_length = len(last_para) + 2
                    else:
                        # Split long paragraph by words for overlap
                        words = last_para.split()
                        overlap_words = words[-overlap:] if len(words) > overlap else words
                        current_chunk = [' '.join(overlap_words)]
                        current_length = len(current_chunk[0]) + 2
                else:
                    current_chunk = []
                    current_length = 0
            
            # If single paragraph exceeds chunk_size, split it by words
            if para_length > chunk_size:
                words = para.split()
                word_chunk = []
                word_length = 0
                
                for word in words:
                    word_len = len(word) + 1  # +1 for space
                    if word_length + word_len > chunk_size and word_chunk:
                        current_chunk.append(' '.join(word_chunk))
                        current_length += len(current_chunk[-1]) + 2
                        
                        # Check if we need to save chunk
                        if current_length > chunk_size:
                            chunks.append('\n\n'.join(current_chunk))
                            # Overlap
                            overlap_words = word_chunk[-overlap:] if len(word_chunk) > overlap else word_chunk
                            current_chunk = [' '.join(overlap_words)]
                            current_length = len(current_chunk[0]) + 2
                        
                        word_chunk = []
                        word_length = 0
                    
                    word_chunk.append(word)
                    word_length += word_len
                
                if word_chunk:
                    current_chunk.append(' '.join(word_chunk))
                    current_length += len(current_chunk[-1]) + 2
            else:
                # Paragraph fits, add it
                current_chunk.append(para)
                current_length += para_length
        
        # Add final chunk
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks if chunks else [content]
    
    async def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search rules content semantically.
        
        Args:
            query: Search query
            n_results: Number of results to return
            
        Returns:
            List of relevant content chunks with metadata
        """
        if not self.embedding_provider:
            return []
        
        try:
            if self.chroma_manager:
                # Use ChromaManager if available
                results = await self.chroma_manager.search(
                    query=query,
                    n_results=n_results,
                    collection_name="rules_content"
                )
                
                # Format results
                formatted_results = []
                if results and results.get('ids') and len(results['ids'][0]) > 0:
                    for i in range(len(results['ids'][0])):
                        formatted_results.append({
                            "content": results['documents'][0][i],
                            "metadata": results['metadatas'][0][i],
                            "distance": results['distances'][0][i] if 'distances' in results else None
                        })
                return formatted_results
            else:
                # Fallback: generate query embedding and search directly
                query_embedding = await self.embedding_provider.generate_single(query, task_type="retrieval_query")
                
                # Search in ChromaDB
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results
                )
                
                # Format results
                formatted_results = []
                if results['ids'] and len(results['ids'][0]) > 0:
                    for i in range(len(results['ids'][0])):
                        formatted_results.append({
                            "content": results['documents'][0][i],
                            "metadata": results['metadatas'][0][i],
                            "distance": results['distances'][0][i] if 'distances' in results else None
                        })
                
                return formatted_results
        except Exception as e:
            print(f"Error searching rules: {e}")
            return []
    
    def delete_file_index(self, file_id: str) -> None:
        """Remove all chunks for a file from the index."""
        try:
            # Get all document IDs for this file
            if self.chroma_manager:
                # Use ChromaManager if available
                results = self.chroma_manager.get(
                    where={"file_id": file_id},
                    collection_name="rules_content"
                )
                if results and results.get('ids') and len(results['ids']) > 0:
                    self.chroma_manager.delete(
                        ids=results['ids'],
                        collection_name="rules_content"
                    )
                    print(f"Deleted {len(results['ids'])} chunks from index for file {file_id}")
                else:
                    print(f"No chunks found in index for file {file_id}")
            else:
                # Fallback: use collection directly
                results = self.collection.get(
                    where={"file_id": file_id}
                )
                if results and results.get('ids') and len(results['ids']) > 0:
                    self.collection.delete(ids=results['ids'])
                    print(f"Deleted {len(results['ids'])} chunks from index for file {file_id}")
                else:
                    print(f"No chunks found in index for file {file_id}")
        except Exception as e:
            print(f"Error deleting file index for {file_id}: {e}")
            raise
    
    def get_all_indexed_files(self) -> List[str]:
        """Get list of all indexed file IDs."""
        results = self.collection.get()
        file_ids = set()
        for metadata in results.get('metadatas', []):
            if 'file_id' in metadata:
                file_ids.add(metadata['file_id'])
        return list(file_ids)

