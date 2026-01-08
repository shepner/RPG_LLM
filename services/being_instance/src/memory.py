"""Memory management for beings."""

import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from shared.vector_store.chroma_manager import ChromaManager
from shared.vector_store.embedding_manager import EmbeddingManager
from shared.embedding_provider.gemini import GeminiEmbeddingProvider
from .memory_events import MemoryEvent, MemoryEventCreate, MemoryEventType, MemoryVisibility


class MemoryManager:
    """Manages being memories with comprehensive event tracking."""
    
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
        """Add a memory (legacy method for backward compatibility)."""
        memory_id = str(uuid.uuid4())
        
        await self.embedding_manager.add_document(
            doc_id=memory_id,
            document=content,
            metadata={"being_id": self.being_id, **(metadata or {})}
        )
    
    async def add_event(self, event: MemoryEventCreate) -> MemoryEvent:
        """
        Add a comprehensive memory event.
        
        This captures everything: incoming messages, outgoing responses,
        thoughts, actions, state changes, etc. with proper metadata.
        """
        event_id = str(uuid.uuid4())
        
        # Create full event
        memory_event = MemoryEvent(
            event_id=event_id,
            being_id=self.being_id,
            event_type=event.event_type,
            visibility=event.visibility,
            content=event.content,
            summary=event.summary,
            timestamp=datetime.now(),
            game_time=event.game_time,
            session_id=event.session_id,
            game_system=event.game_system,
            source_being_id=event.source_being_id,
            target_being_id=event.target_being_id,
            related_event_ids=event.related_event_ids or [],
            metadata=event.metadata or {}
        )
        
        # Build comprehensive metadata for vector store
        vector_metadata = {
            "being_id": self.being_id,
            "event_id": event_id,
            "event_type": event.event_type.value,
            "visibility": event.visibility.value,
            "timestamp": memory_event.timestamp.isoformat(),
        }
        
        # Add optional fields
        if event.game_time is not None:
            vector_metadata["game_time"] = event.game_time
        if event.session_id:
            vector_metadata["session_id"] = event.session_id
        if event.game_system:
            vector_metadata["game_system"] = event.game_system
        if event.source_being_id:
            vector_metadata["source_being_id"] = event.source_being_id
        if event.target_being_id:
            vector_metadata["target_being_id"] = event.target_being_id
        if event.related_event_ids:
            vector_metadata["related_event_ids"] = ",".join(event.related_event_ids)
        
        # Add event-specific metadata
        if event.metadata:
            # Flatten nested metadata for vector store (ChromaDB prefers flat structures)
            for key, value in event.metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    vector_metadata[f"meta_{key}"] = value
                else:
                    vector_metadata[f"meta_{key}"] = str(value)
        
        # Build document text (include summary if available for better searchability)
        document_text = event.content
        if event.summary:
            document_text = f"{event.summary}\n\n{event.content}"
        
        # Store in vector store
        await self.embedding_manager.add_document(
            doc_id=event_id,
            document=document_text,
            metadata=vector_metadata
        )
        
        return memory_event
    
    async def add_incoming_message(
        self,
        content: str,
        source_being_id: Optional[str] = None,
        session_id: Optional[str] = None,
        game_system: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryEvent:
        """Record an incoming message to the being."""
        return await self.add_event(MemoryEventCreate(
            event_type=MemoryEventType.INCOMING_MESSAGE,
            visibility=MemoryVisibility.PUBLIC,
            content=content,
            session_id=session_id,
            game_system=game_system,
            source_being_id=source_being_id,
            metadata=metadata or {}
        ))
    
    async def add_outgoing_response(
        self,
        content: str,
        target_being_id: Optional[str] = None,
        session_id: Optional[str] = None,
        game_system: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryEvent:
        """Record an outgoing response from the being."""
        return await self.add_event(MemoryEventCreate(
            event_type=MemoryEventType.OUTGOING_RESPONSE,
            visibility=MemoryVisibility.PUBLIC,
            content=content,
            session_id=session_id,
            game_system=game_system,
            target_being_id=target_being_id,
            metadata=metadata or {}
        ))
    
    async def add_thought(
        self,
        content: str,
        game_time: Optional[float] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryEvent:
        """Record an internal thought (private to the being)."""
        return await self.add_event(MemoryEventCreate(
            event_type=MemoryEventType.OUTGOING_THOUGHT,
            visibility=MemoryVisibility.PRIVATE,
            content=content,
            game_time=game_time,
            session_id=session_id,
            metadata=metadata or {}
        ))
    
    async def add_action(
        self,
        content: str,
        action_type: str,
        game_time: Optional[float] = None,
        session_id: Optional[str] = None,
        target_being_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryEvent:
        """Record an action taken by the being."""
        action_metadata = {"action_type": action_type, **(metadata or {})}
        return await self.add_event(MemoryEventCreate(
            event_type=MemoryEventType.OUTGOING_ACTION,
            visibility=MemoryVisibility.PUBLIC,
            content=content,
            game_time=game_time,
            session_id=session_id,
            target_being_id=target_being_id,
            metadata=action_metadata
        ))
    
    async def add_state_change(
        self,
        content: str,
        change_type: str,
        old_value: Any = None,
        new_value: Any = None,
        game_time: Optional[float] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryEvent:
        """Record a state change (something done TO the being)."""
        state_metadata = {
            "change_type": change_type,
            **(metadata or {})
        }
        if old_value is not None:
            state_metadata["old_value"] = str(old_value)
        if new_value is not None:
            state_metadata["new_value"] = str(new_value)
        
        return await self.add_event(MemoryEventCreate(
            event_type=MemoryEventType.STATE_CHANGE,
            visibility=MemoryVisibility.PUBLIC,
            content=content,
            game_time=game_time,
            session_id=session_id,
            metadata=state_metadata
        ))
    
    async def search_memories(
        self,
        query: str,
        n_results: int = 10,
        event_types: Optional[List[MemoryEventType]] = None,
        visibility: Optional[MemoryVisibility] = None,
        include_private: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search memories with filtering options.
        
        Args:
            query: Search query
            n_results: Number of results
            event_types: Filter by event types
            visibility: Filter by visibility
            include_private: Whether to include private thoughts (if False, only public)
        """
        where_clause = {"being_id": self.being_id}
        
        if event_types:
            where_clause["event_type"] = {"$in": [et.value for et in event_types]}
        
        if visibility:
            where_clause["visibility"] = visibility.value
        elif not include_private:
            where_clause["visibility"] = MemoryVisibility.PUBLIC.value
        
        results = await self.embedding_manager.search(
            query=query,
            n_results=n_results,
            where=where_clause
        )
        return results
    
    async def get_recent_events(
        self,
        n_results: int = 50,
        event_types: Optional[List[MemoryEventType]] = None,
        include_private: bool = True
    ) -> List[Dict[str, Any]]:
        """Get recent events (by timestamp)."""
        # Search with a broad query to get recent items
        results = await self.search_memories(
            query="recent events",
            n_results=n_results,
            event_types=event_types,
            include_private=include_private
        )
        
        # Sort by timestamp if available
        if results and "metadatas" in results:
            # Note: ChromaDB doesn't natively support timestamp sorting
            # This would need to be done in application code or via metadata filtering
            pass
        
        return results

