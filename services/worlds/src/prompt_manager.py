"""System prompt manager for LLM services."""

import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, DateTime, JSON, Enum as SQLEnum
import sqlalchemy as sa

from .models import SystemPrompt, SystemPromptCreate, SystemPromptUpdate, PromptScope

Base = declarative_base()


class SystemPromptDB(Base):
    """System prompt database model."""
    
    __tablename__ = "system_prompts"
    
    prompt_id = Column(String, primary_key=True)
    service_name = Column(String, nullable=False)  # "rules_engine", "game_master", "being"
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    scope = Column(SQLEnum(PromptScope), default=PromptScope.GLOBAL)
    session_ids = Column(String)  # JSON array of session IDs
    game_system = Column(String)  # Optional game system tag
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    prompt_metadata = Column(JSON, default={})  # Renamed from 'metadata' to avoid SQLAlchemy conflict


class PromptManager:
    """Manages system prompts for LLM services."""
    
    def __init__(self, database_url: str, service_name: str = "worlds"):
        """
        Initialize prompt manager.
        
        Args:
            database_url: SQLite database URL
            service_name: Name of the service (e.g., "rules_engine", "game_master", "being")
        """
        self.database_url = database_url
        self.service_name = service_name
        self.engine = create_async_engine(database_url, echo=False)
        self.SessionLocal = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def init_db(self):
        """Initialize database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def create_prompt(self, prompt_data: SystemPromptCreate) -> SystemPrompt:
        """Create a new system prompt."""
        import json
        
        async with self.SessionLocal() as session:
            prompt_id = str(uuid.uuid4())
            prompt_db = SystemPromptDB(
                prompt_id=prompt_id,
                service_name=self.service_name,
                title=prompt_data.title,
                content=prompt_data.content,
                scope=prompt_data.scope,
                session_ids=json.dumps(prompt_data.session_ids) if prompt_data.session_ids else "[]",
                game_system=prompt_data.game_system,
                prompt_metadata=prompt_data.metadata
            )
            session.add(prompt_db)
            await session.commit()
            await session.refresh(prompt_db)
            
            return self._db_to_model(prompt_db)
    
    async def get_prompt(self, prompt_id: str) -> Optional[SystemPrompt]:
        """Get a system prompt by ID."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                sa.select(SystemPromptDB).where(
                    sa.and_(
                        SystemPromptDB.prompt_id == prompt_id,
                        SystemPromptDB.service_name == self.service_name
                    )
                )
            )
            prompt_db = result.scalar_one_or_none()
            return self._db_to_model(prompt_db) if prompt_db else None
    
    async def list_prompts(
        self,
        session_id: Optional[str] = None,
        game_system: Optional[str] = None,
        include_global: bool = True
    ) -> List[SystemPrompt]:
        """
        List system prompts.
        
        Args:
            session_id: Filter by session ID (returns global + session-specific)
            game_system: Filter by game system
            include_global: Whether to include global prompts
        """
        import json
        
        async with self.SessionLocal() as session:
            query = sa.select(SystemPromptDB).where(
                SystemPromptDB.service_name == self.service_name
            )
            
            # Filter by game system if provided
            if game_system:
                query = query.where(SystemPromptDB.game_system == game_system)
            
            # Filter by scope
            if session_id:
                # Include global prompts and session-specific prompts
                if include_global:
                    query = query.where(
                        sa.or_(
                            SystemPromptDB.scope == PromptScope.GLOBAL,
                            SystemPromptDB.session_ids.contains(f'"{session_id}"')
                        )
                    )
                else:
                    query = query.where(SystemPromptDB.session_ids.contains(f'"{session_id}"'))
            elif not include_global:
                # Only session-scoped prompts (no specific session)
                query = query.where(SystemPromptDB.scope == PromptScope.SESSION)
            
            result = await session.execute(query.order_by(SystemPromptDB.created_at.desc()))
            prompts_db = result.scalars().all()
            
            return [self._db_to_model(p) for p in prompts_db]
    
    async def update_prompt(self, prompt_id: str, prompt_data: SystemPromptUpdate) -> Optional[SystemPrompt]:
        """Update a system prompt."""
        import json
        
        async with self.SessionLocal() as session:
            result = await session.execute(
                sa.select(SystemPromptDB).where(
                    sa.and_(
                        SystemPromptDB.prompt_id == prompt_id,
                        SystemPromptDB.service_name == self.service_name
                    )
                )
            )
            prompt_db = result.scalar_one_or_none()
            
            if not prompt_db:
                return None
            
            # Update fields
            if prompt_data.title is not None:
                prompt_db.title = prompt_data.title
            if prompt_data.content is not None:
                prompt_db.content = prompt_data.content
            if prompt_data.scope is not None:
                prompt_db.scope = prompt_data.scope
            if prompt_data.session_ids is not None:
                prompt_db.session_ids = json.dumps(prompt_data.session_ids) if prompt_data.session_ids else "[]"
            if prompt_data.game_system is not None:
                prompt_db.game_system = prompt_data.game_system
            if prompt_data.metadata is not None:
                prompt_db.prompt_metadata = prompt_data.metadata
            
            prompt_db.updated_at = datetime.now()
            
            await session.commit()
            await session.refresh(prompt_db)
            
            return self._db_to_model(prompt_db)
    
    async def delete_prompt(self, prompt_id: str) -> bool:
        """Delete a system prompt."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                sa.select(SystemPromptDB).where(
                    sa.and_(
                        SystemPromptDB.prompt_id == prompt_id,
                        SystemPromptDB.service_name == self.service_name
                    )
                )
            )
            prompt_db = result.scalar_one_or_none()
            
            if not prompt_db:
                return False
            
            await session.delete(prompt_db)
            await session.commit()
            return True
    
    async def get_active_prompts(
        self,
        session_id: Optional[str] = None,
        game_system: Optional[str] = None
    ) -> str:
        """
        Get combined active system prompts as a single string.
        This is what should be prepended to the system_prompt when calling LLM.
        
        Args:
            session_id: Current session ID (if any)
            game_system: Current game system (if any)
        
        Returns:
            Combined prompt text, or empty string if none
        """
        prompts = await self.list_prompts(
            session_id=session_id,
            game_system=game_system,
            include_global=True
        )
        
        if not prompts:
            return ""
        
        # Combine all prompts
        combined = "\n\n".join([f"## {p.title}\n{p.content}" for p in prompts])
        return combined
    
    def _db_to_model(self, prompt_db: SystemPromptDB) -> SystemPrompt:
        """Convert database model to Pydantic model."""
        import json
        
        session_ids = []
        if prompt_db.session_ids:
            try:
                session_ids = json.loads(prompt_db.session_ids)
            except:
                session_ids = []
        
        return SystemPrompt(
            prompt_id=prompt_db.prompt_id,
            service_name=prompt_db.service_name,
            title=prompt_db.title,
            content=prompt_db.content,
            scope=prompt_db.scope,
            session_ids=session_ids,
            game_system=prompt_db.game_system,
            created_at=prompt_db.created_at,
            updated_at=prompt_db.updated_at,
            metadata=prompt_db.prompt_metadata or {}
        )

