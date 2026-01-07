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
            self.embedding_provider = GeminiEmbeddingProvider()
        except Exception as e:
            print(f"Warning: Embedding provider not available: {e}")
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
        chunks = self._chunk_content(content, chunk_size=1000, overlap=200)
        total_chunks = len(chunks)
        
        # Report progress: chunking complete
        if progress_callback:
            progress_callback(0, total_chunks, "chunking")
        
        # Generate embeddings and store
        try:
            # Report progress: generating embeddings
            if progress_callback:
                progress_callback(0, total_chunks, "generating_embeddings")
            
            # Generate embeddings for all chunks at once
            embeddings_response = await self.embedding_provider.generate(chunks)
            embeddings = embeddings_response.embeddings
            
            # Report progress: embeddings generated
            if progress_callback:
                progress_callback(total_chunks // 2, total_chunks, "preparing_data")
            
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
            
            # Report progress: data prepared, now storing
            if progress_callback:
                progress_callback(int(total_chunks * 0.9), total_chunks, "storing")
            
            # Add to ChromaDB collection
            self.collection.add(
                ids=chunk_ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=chunk_metadatas
            )
            
            # Report progress: complete
            if progress_callback:
                progress_callback(total_chunks, total_chunks, "complete")
        except Exception as e:
            print(f"Warning: Failed to index file {filename}: {e}")
            if progress_callback:
                progress_callback(0, total_chunks, "error")
            raise
    
    def _chunk_content(self, content: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split content into overlapping chunks."""
        chunks = []
        words = content.split()
        
        current_chunk = []
        current_length = 0
        
        for word in words:
            word_length = len(word) + 1  # +1 for space
            
            if current_length + word_length > chunk_size and current_chunk:
                # Save current chunk
                chunks.append(' '.join(current_chunk))
                
                # Start new chunk with overlap
                overlap_words = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                current_chunk = overlap_words
                current_length = sum(len(w) + 1 for w in current_chunk)
            
            current_chunk.append(word)
            current_length += word_length
        
        # Add final chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
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

