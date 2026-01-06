"""Time management service models."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum

from shared.models.common import GameTime


class TimeMode(str, Enum):
    """Time progression mode."""
    
    REAL_TIME = "real-time"
    TURN_BASED = "turn-based"


class TimeStatus(str, Enum):
    """Time progression status."""
    
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class HistoricalEvent(BaseModel):
    """Historical event model."""
    
    event_id: str
    timestamp: float
    event_type: str
    description: str
    created_by: str
    event_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

