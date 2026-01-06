"""Memory management for beings."""

import os
from typing import List, Dict, Any, Optional
from shared.vector_store.chroma_manager import ChromaManager
from shared.vector_store.embedding_manager import EmbeddingManager
from shared.embedding_provider.gemini import GeminiEmbeddingProvider


class MemoryManager:
    """Manages being memories."""
    
    def __init__(self, being_id: str, chroma_path: str):
        """Initialize memory manager."""
        self.being_id = being_id
        
        # Initialize vector store
        chroma_manager = ChromaManager(
            collection_name=f"being_{being_id}_memories",
            persist_directory=chroma_path
        )
        
        embedding_provider = GeminiEmbeddingProvider(
            api_key=os.getenv("GEMINI_API_KEY")
        )
        
        self.embedding_manager = EmbeddingManager(embedding_provider, chroma_manager)
    
    async def add_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add a memory."""
        import uuid
        memory_id = str(uuid.uuid4())
        
        await self.embedding_manager.add_document(
            doc_id=memory_id,
            document=content,
            metadata={"being_id": self.being_id, **(metadata or {})}
        )
    
    async def search_memories(
        self,
        query: str,
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search memories."""
        results = await self.embedding_manager.search(
            query=query,
            n_results=n_results,
            where={"being_id": self.being_id}
        )
        return results

