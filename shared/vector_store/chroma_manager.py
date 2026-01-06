"""ChromaDB vector store manager."""

import os
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions


class ChromaManager:
    """Manages ChromaDB collections for semantic memory storage."""
    
    def __init__(
        self,
        collection_name: str,
        persist_directory: Optional[str] = None,
        embedding_function=None,
        client: Optional[chromadb.Client] = None
    ):
        """
        Initialize ChromaDB manager.
        
        Args:
            collection_name: Name of the ChromaDB collection
            persist_directory: Directory to persist ChromaDB data
            embedding_function: Embedding function to use (if None, uses default)
            client: Optional existing ChromaDB client
        """
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        
        # Initialize ChromaDB client
        if client:
            self.client = client
        else:
            if persist_directory:
                self.client = chromadb.PersistentClient(
                    path=persist_directory,
                    settings=Settings(anonymized_telemetry=False)
                )
            else:
                self.client = chromadb.Client(
                    settings=Settings(anonymized_telemetry=False)
                )
        
        # Get or create collection
        if embedding_function:
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=embedding_function
            )
        else:
            # Use default embedding function (sentence-transformers)
            default_ef = embedding_functions.DefaultEmbeddingFunction()
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=default_ef
            )
    
    def add(
        self,
        ids: List[str],
        documents: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Add documents to the collection.
        
        Args:
            ids: List of unique IDs for documents
            documents: List of document texts
            embeddings: Optional pre-computed embeddings (if None, will be computed)
            metadatas: Optional metadata for each document
        """
        if embeddings:
            self.collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
        else:
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
    
    def query(
        self,
        query_texts: Optional[List[str]] = None,
        query_embeddings: Optional[List[List[float]]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Query the collection.
        
        Args:
            query_texts: Query texts (will be embedded)
            query_embeddings: Optional pre-computed query embeddings
            n_results: Number of results to return
            where: Metadata filter
            where_document: Document content filter
            include: What to include in results (documents, metadatas, distances, etc.)
            
        Returns:
            Query results dictionary
        """
        if include is None:
            include = ["documents", "metadatas", "distances"]
        
        if query_embeddings:
            results = self.collection.query(
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where,
                where_document=where_document,
                include=include
            )
        else:
            results = self.collection.query(
                query_texts=query_texts,
                n_results=n_results,
                where=where,
                where_document=where_document,
                include=include
            )
        
        return results
    
    def get(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        include: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get documents from the collection.
        
        Args:
            ids: Optional list of IDs to retrieve
            where: Metadata filter
            where_document: Document content filter
            limit: Maximum number of results
            offset: Offset for pagination
            include: What to include in results
            
        Returns:
            Retrieved documents dictionary
        """
        if include is None:
            include = ["documents", "metadatas"]
        
        return self.collection.get(
            ids=ids,
            where=where,
            where_document=where_document,
            limit=limit,
            offset=offset,
            include=include
        )
    
    def update(
        self,
        ids: List[str],
        documents: Optional[List[str]] = None,
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Update documents in the collection.
        
        Args:
            ids: List of IDs to update
            documents: Optional new document texts
            embeddings: Optional new embeddings
            metadatas: Optional new metadata
        """
        self.collection.update(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )
    
    def delete(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ):
        """
        Delete documents from the collection.
        
        Args:
            ids: Optional list of IDs to delete
            where: Metadata filter for deletion
            where_document: Document content filter for deletion
        """
        self.collection.delete(
            ids=ids,
            where=where,
            where_document=where_document
        )
    
    def count(self) -> int:
        """Get the number of documents in the collection."""
        return self.collection.count()
    
    def peek(self, limit: int = 10) -> Dict[str, Any]:
        """Peek at documents in the collection."""
        return self.collection.peek(limit=limit)

