"""Game event models and types."""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from .common import GameTime, EventType, EventSeverity


class NarrativeEvent(BaseModel):
    """Narrative event from Game Master service."""
    
    event_id: str
    game_time: GameTime
    narrative_text: str
    scene_id: Optional[str] = None
    characters_involved: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorldEvolutionEvent(BaseModel):
    """World evolution event (natural processes, infrastructure decay, etc.)."""
    
    event_id: str
    game_time: GameTime
    process_type: str  # erosion, decay, growth, weather, etc.
    affected_location: Optional[str] = None
    description: str
    changes: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BeingActionEvent(BaseModel):
    """Event representing a being's action."""
    
    event_id: str
    being_id: str
    game_time: GameTime
    action_type: str
    description: str
    thoughts: Optional[str] = None  # Associated thoughts
    outcome: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

