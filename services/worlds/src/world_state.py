"""World state manager."""

import os
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Float, JSON, DateTime
import sqlalchemy as sa
from datetime import datetime

from shared.vector_store.chroma_manager import ChromaManager
from shared.vector_store.embedding_manager import EmbeddingManager
from shared.embedding_provider.gemini import GeminiEmbeddingProvider
from .models import WorldEvent

Base = declarative_base()


class EventDB(Base):
    """Event database model."""
    
    __tablename__ = "events"
    
    event_id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    description = Column(String, nullable=False)
    game_time = Column(Float, nullable=False)
    event_metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.now)


class WorldStateManager:
    """Manages world state and events."""
    
    def __init__(self, database_url: str, chroma_path: str, embedding_provider):
        """Initialize world state manager."""
        self.database_url = database_url
        self.engine = create_async_engine(database_url, echo=False)
        self.SessionLocal = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        
        # Initialize vector store
        chroma_manager = ChromaManager(
            collection_name="world_events",
            persist_directory=chroma_path
        )
        self.embedding_manager = EmbeddingManager(embedding_provider, chroma_manager)
    
    async def init_db(self):
        """Initialize database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def record_event(
        self,
        event_type: str,
        description: str,
        game_time: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> WorldEvent:
        """Record a world event."""
        event_id = str(uuid.uuid4())
        
        async with self.SessionLocal() as session:
            event_db = EventDB(
                event_id=event_id,
                event_type=event_type,
                description=description,
                game_time=game_time,
                event_metadata=metadata or {}
            )
            session.add(event_db)
            await session.commit()
        
        # Store in vector store (async, non-blocking)
        event_metadata = dict(metadata) if metadata else {}
        event_metadata.update({"event_type": event_type, "game_time": game_time})
        await self.embedding_manager.add_document(
            doc_id=event_id,
            document=description,
            metadata=event_metadata
        )
        
        return WorldEvent(
            event_id=event_id,
            event_type=event_type,
            description=description,
            game_time=game_time,
            metadata=metadata or {}
        )
    
    async def search_events(
        self,
        query: str,
        n_results: int = 10,
        time_range: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """Search events semantically."""
        where = {}
        if time_range:
            where = {"game_time": {"$gte": time_range[0], "$lte": time_range[1]}}
        
        results = await self.embedding_manager.search(
            query=query,
            n_results=n_results,
            where=where
        )
        
        return results

