"""Time management engine."""

import os
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Float, DateTime, JSON
import sqlalchemy as sa

from .models import GameTime, TimeMode, TimeStatus, HistoricalEvent

Base = declarative_base()


class GameTimeDB(Base):
    """Game time database model."""
    
    __tablename__ = "game_time"
    
    session_id = Column(String, primary_key=True)
    current_time = Column(Float, default=0.0)
    time_scale = Column(Float, default=1.0)
    mode = Column(String, default="real-time")
    status = Column(String, default="stopped")
    turn_number = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class HistoricalEventDB(Base):
    """Historical event database model."""
    
    __tablename__ = "historical_events"
    
    event_id = Column(String, primary_key=True)
    timestamp = Column(Float, nullable=False)
    event_type = Column(String, nullable=False)
    description = Column(String)
    created_by = Column(String, nullable=False)
    event_metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.now)


class TimeEngine:
    """Manages game time progression."""
    
    def __init__(self, database_url: str):
        """Initialize time engine."""
        self.database_url = database_url
        self.engine = create_async_engine(database_url, echo=False)
        self.SessionLocal = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        self._running_tasks: Dict[str, asyncio.Task] = {}
    
    async def init_db(self):
        """Initialize database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def get_current_time(self, session_id: str) -> Optional[GameTime]:
        """Get current game time for a session."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                sa.select(GameTimeDB).where(GameTimeDB.session_id == session_id)
            )
            time_db = result.scalar_one_or_none()
            
            if not time_db:
                return None
            
            return GameTime(
                timestamp=time_db.current_time,
                real_world_time=datetime.now(),
                time_scale=time_db.time_scale,
                mode=time_db.mode,
                turn_number=int(time_db.turn_number) if time_db.turn_number else None
            )
    
    async def advance_time(self, session_id: str, amount: float):
        """Advance game time."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                sa.select(GameTimeDB).where(GameTimeDB.session_id == session_id)
            )
            time_db = result.scalar_one_or_none()
            
            if not time_db:
                time_db = GameTimeDB(session_id=session_id, current_time=0.0)
                session.add(time_db)
            
            time_db.current_time += amount
            await session.commit()

