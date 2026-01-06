"""Embedding generation and management."""

from typing import List, Dict, Any, Optional
from ..embedding_provider.base import BaseEmbeddingProvider
from .chroma_manager import ChromaManager


class EmbeddingManager:
    """Manages embedding generation and storage."""
    
    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider,
        chroma_manager: ChromaManager
    ):
        """
        Initialize embedding manager.
        
        Args:
            embedding_provider: Embedding provider instance
            chroma_manager: ChromaDB manager instance
        """
        self.embedding_provider = embedding_provider
        self.chroma_manager = chroma_manager
    
    async def add_documents(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        generate_embeddings: bool = True
    ):
        """
        Add documents with optional embedding generation.
        
        Args:
            ids: List of unique IDs
            documents: List of document texts
            metadatas: Optional metadata for each document
            generate_embeddings: Whether to generate embeddings (if False, ChromaDB will generate)
        """
        embeddings = None
        if generate_embeddings:
            response = await self.embedding_provider.generate(documents)
            embeddings = response.embeddings
        
        self.chroma_manager.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )
    
    async def add_document(
        self,
        doc_id: str,
        document: str,
        metadata: Optional[Dict[str, Any]] = None,
        generate_embedding: bool = True
    ):
        """
        Add a single document.
        
        Args:
            doc_id: Unique document ID
            document: Document text
            metadata: Optional metadata
            generate_embedding: Whether to generate embedding
        """
        await self.add_documents(
            ids=[doc_id],
            documents=[document],
            metadatas=[metadata] if metadata else None,
            generate_embeddings=generate_embedding
        )
    
    async def search(
        self,
        query: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Search for similar documents.
        
        Args:
            query: Search query text
            n_results: Number of results to return
            where: Metadata filter
            where_document: Document content filter
            
        Returns:
            Search results dictionary
        """
        return self.chroma_manager.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
            where_document=where_document
        )
    
    async def search_by_embedding(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Search using a pre-computed embedding.
        
        Args:
            query_embedding: Query embedding vector
            n_results: Number of results to return
            where: Metadata filter
            where_document: Document content filter
            
        Returns:
            Search results dictionary
        """
        return self.chroma_manager.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            where_document=where_document
        )

