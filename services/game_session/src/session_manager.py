"""Game session manager."""

import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, DateTime, JSON, Enum as SQLEnum
import sqlalchemy as sa

from .models import GameSession, SessionStatus, TimeMode, SessionState

Base = declarative_base()


class GameSessionDB(Base):
    """Game session database model."""
    
    __tablename__ = "game_sessions"
    
    session_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    gm_user_id = Column(String, nullable=False)
    player_user_ids = Column(String)  # JSON string
    status = Column(SQLEnum(SessionStatus), default=SessionStatus.CREATED)
    worlds_service_url = Column(String)
    time_management_service_url = Column(String)
    game_system_type = Column(String)
    time_mode_preference = Column(SQLEnum(TimeMode), default=TimeMode.REAL_TIME)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    settings = Column(JSON, default={})


class SessionManager:
    """Manages game sessions."""
    
    def __init__(self, database_url: str):
        """Initialize session manager."""
        self.database_url = database_url
        self.engine = create_async_engine(database_url, echo=False)
        self.SessionLocal = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def init_db(self):
        """Initialize database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def create_session(
        self,
        name: str,
        gm_user_id: str,
        description: Optional[str] = None,
        game_system_type: Optional[str] = None,
        time_mode_preference: TimeMode = TimeMode.REAL_TIME,
        settings: Optional[Dict[str, Any]] = None
    ) -> GameSession:
        """Create a new game session."""
        import json
        
        session_id = str(uuid.uuid4())
        
        async with self.SessionLocal() as session:
            session_db = GameSessionDB(
                session_id=session_id,
                name=name,
                description=description,
                gm_user_id=gm_user_id,
                player_user_ids=json.dumps([]),
                status=SessionStatus.CREATED,
                game_system_type=game_system_type,
                time_mode_preference=time_mode_preference,
                settings=settings or {}
            )
            
            session.add(session_db)
            await session.commit()
            await session.refresh(session_db)
            
            return self._db_to_model(session_db)
    
    async def get_session(self, session_id: str) -> Optional[GameSession]:
        """Get session by ID."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                sa.select(GameSessionDB).where(GameSessionDB.session_id == session_id)
            )
            session_db = result.scalar_one_or_none()
            
            if not session_db:
                return None
            
            return self._db_to_model(session_db)
    
    async def join_session(self, session_id: str, user_id: str) -> bool:
        """Add player to session."""
        import json
        
        async with self.SessionLocal() as session:
            result = await session.execute(
                sa.select(GameSessionDB).where(GameSessionDB.session_id == session_id)
            )
            session_db = result.scalar_one_or_none()
            
            if not session_db:
                return False
            
            player_ids = json.loads(session_db.player_user_ids or "[]")
            if user_id not in player_ids:
                player_ids.append(user_id)
                session_db.player_user_ids = json.dumps(player_ids)
                await session.commit()
            
            return True
    
    async def leave_session(self, session_id: str, user_id: str) -> bool:
        """Remove player from session."""
        import json
        
        async with self.SessionLocal() as session:
            result = await session.execute(
                sa.select(GameSessionDB).where(GameSessionDB.session_id == session_id)
            )
            session_db = result.scalar_one_or_none()
            
            if not session_db:
                return False
            
            player_ids = json.loads(session_db.player_user_ids or "[]")
            if user_id in player_ids:
                player_ids.remove(user_id)
                session_db.player_user_ids = json.dumps(player_ids)
                await session.commit()
            
            return True
    
    async def update_session(
        self,
        session_id: str,
        session_data: "SessionUpdate"
    ) -> Optional[GameSession]:
        """Update a game session."""
        from .models import SessionUpdate
        
        async with self.SessionLocal() as session:
            result = await session.execute(
                sa.select(GameSessionDB).where(GameSessionDB.session_id == session_id)
            )
            session_db = result.scalar_one_or_none()
            
            if not session_db:
                return None
            
            # Update fields if provided
            if session_data.name is not None:
                session_db.name = session_data.name
            if session_data.description is not None:
                session_db.description = session_data.description
            if session_data.game_system_type is not None:
                session_db.game_system_type = session_data.game_system_type
            if session_data.time_mode_preference is not None:
                session_db.time_mode_preference = session_data.time_mode_preference
            if session_data.status is not None:
                session_db.status = session_data.status
            if session_data.settings is not None:
                session_db.settings = session_data.settings
            
            session_db.updated_at = datetime.now()
            await session.commit()
            await session.refresh(session_db)
            
            return self._db_to_model(session_db)
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a game session."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                sa.select(GameSessionDB).where(GameSessionDB.session_id == session_id)
            )
            session_db = result.scalar_one_or_none()
            
            if not session_db:
                return False
            
            await session.delete(session_db)
            await session.commit()
            return True
    
    async def list_sessions(
        self,
        user_id: Optional[str] = None,
        status: Optional[SessionStatus] = None
    ) -> List[GameSession]:
        """List game sessions, optionally filtered by user or status."""
        async with self.SessionLocal() as session:
            query = sa.select(GameSessionDB)
            
            if user_id:
                # Filter by user being GM or player
                query = query.where(
                    (GameSessionDB.gm_user_id == user_id) |
                    (GameSessionDB.player_user_ids.contains(f'"{user_id}"'))
                )
            
            if status:
                query = query.where(GameSessionDB.status == status)
            
            result = await session.execute(query)
            sessions_db = result.scalars().all()
            
            return [self._db_to_model(session_db) for session_db in sessions_db]
    
    def _db_to_model(self, session_db: GameSessionDB) -> GameSession:
        """Convert database model to Pydantic model."""
        import json
        
        return GameSession(
            session_id=session_db.session_id,
            name=session_db.name,
            description=session_db.description,
            gm_user_id=session_db.gm_user_id,
            player_user_ids=json.loads(session_db.player_user_ids or "[]"),
            status=session_db.status,
            worlds_service_url=session_db.worlds_service_url,
            time_management_service_url=session_db.time_management_service_url,
            game_system_type=session_db.game_system_type,
            time_mode_preference=session_db.time_mode_preference,
            created_at=session_db.created_at,
            updated_at=session_db.updated_at,
            settings=session_db.settings or {}
        )

