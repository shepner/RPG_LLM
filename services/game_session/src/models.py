"""Game session service models."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class SessionStatus(str, Enum):
    """Game session status."""
    
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class TimeMode(str, Enum):
    """Time progression mode."""
    
    REAL_TIME = "real-time"
    TURN_BASED = "turn-based"


class GameSession(BaseModel):
    """Game session model."""
    
    session_id: str
    name: str
    description: Optional[str] = None
    gm_user_id: str
    player_user_ids: List[str] = Field(default_factory=list)
    status: SessionStatus = SessionStatus.CREATED
    worlds_service_url: Optional[str] = None
    time_management_service_url: Optional[str] = None
    game_system_type: Optional[str] = None  # D&D, Pathfinder, custom, etc.
    time_mode_preference: TimeMode = TimeMode.REAL_TIME
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    settings: Dict[str, Any] = Field(default_factory=dict)


class SessionPlayer(BaseModel):
    """Session player model."""
    
    session_id: str
    user_id: str
    joined_at: datetime = Field(default_factory=datetime.now)


class SessionState(BaseModel):
    """Session state model."""
    
    session_id: str
    status: SessionStatus
    current_players: List[str] = Field(default_factory=list)
    game_time: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionCreate(BaseModel):
    """Session creation model."""
    
    name: str
    description: Optional[str] = None
    game_system_type: Optional[str] = None
    time_mode_preference: TimeMode = TimeMode.REAL_TIME
    settings: Dict[str, Any] = Field(default_factory=dict)

