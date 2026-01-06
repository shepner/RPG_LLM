"""Common data models shared across services."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class GameTime(BaseModel):
    """Game time representation."""
    
    timestamp: float = Field(..., description="Game time timestamp (seconds since game start)")
    real_world_time: datetime = Field(default_factory=datetime.now, description="Real-world time reference")
    time_scale: float = Field(default=1.0, description="Time scale multiplier (1.0 = real-time)")
    mode: str = Field(default="real-time", description="Time mode: 'real-time' or 'turn-based'")
    turn_number: Optional[int] = Field(None, description="Current turn number (turn-based mode)")


class EventType(str, Enum):
    """Types of game events."""
    
    ACTION = "action"
    NARRATIVE = "narrative"
    WORLD_CHANGE = "world_change"
    BEING_ACTION = "being_action"
    BEING_THOUGHT = "being_thought"
    WORLD_EVOLUTION = "world_evolution"
    TIME_PROGRESSION = "time_progression"
    RULE_VALIDATION = "rule_validation"
    HISTORICAL = "historical"


class EventSeverity(str, Enum):
    """Event severity levels."""
    
    TRIVIAL = "trivial"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class GameEvent(BaseModel):
    """Standardized game event structure."""
    
    event_id: str = Field(..., description="Unique event identifier")
    event_type: EventType = Field(..., description="Type of event")
    severity: EventSeverity = Field(default=EventSeverity.MODERATE, description="Event severity")
    game_time: GameTime = Field(..., description="Game time when event occurred")
    description: str = Field(..., description="Human-readable event description")
    source_service: str = Field(..., description="Service that generated the event")
    source_entity: Optional[str] = Field(None, description="Entity that caused the event (being_id, etc.)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional event metadata")
    created_at: datetime = Field(default_factory=datetime.now, description="Real-world creation time")


class Action(BaseModel):
    """Player/NPC action representation."""
    
    action_id: str = Field(..., description="Unique action identifier")
    being_id: str = Field(..., description="ID of being performing the action")
    action_type: str = Field(..., description="Type of action (move, attack, cast, etc.)")
    description: str = Field(..., description="Human-readable action description")
    game_time: GameTime = Field(..., description="Game time when action occurred")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    validated: bool = Field(default=False, description="Whether action has been validated")
    validation_results: Dict[str, Any] = Field(default_factory=dict, description="Validation results from services")
    outcome: Optional[str] = Field(None, description="Action outcome description")
    created_at: datetime = Field(default_factory=datetime.now, description="Real-world creation time")


class WorldState(BaseModel):
    """Snapshot of world state."""
    
    state_id: str = Field(..., description="Unique state identifier")
    game_time: GameTime = Field(..., description="Game time of this state snapshot")
    locations: List[Dict[str, Any]] = Field(default_factory=list, description="List of locations in the world")
    entities: List[Dict[str, Any]] = Field(default_factory=list, description="List of entities in the world")
    relationships: List[Dict[str, Any]] = Field(default_factory=list, description="Entity relationships")
    geography: Dict[str, Any] = Field(default_factory=dict, description="Geographic state")
    physical_laws: Dict[str, Any] = Field(default_factory=dict, description="Physical laws and rules")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional state metadata")
    created_at: datetime = Field(default_factory=datetime.now, description="Real-world creation time")


class BeingState(BaseModel):
    """Character/entity state."""
    
    being_id: str = Field(..., description="Unique being identifier")
    game_time: GameTime = Field(..., description="Game time of this state snapshot")
    name: str = Field(..., description="Being name")
    location: Optional[str] = Field(None, description="Current location ID")
    stats: Dict[str, Any] = Field(default_factory=dict, description="Character stats")
    skills: Dict[str, Any] = Field(default_factory=dict, description="Character skills")
    inventory: List[Dict[str, Any]] = Field(default_factory=list, description="Inventory items")
    status: Dict[str, Any] = Field(default_factory=dict, description="Status effects, conditions, etc.")
    goals: List[Dict[str, Any]] = Field(default_factory=list, description="Current goals")
    needs: Dict[str, Any] = Field(default_factory=dict, description="Current needs (hunger, rest, etc.)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional being metadata")
    created_at: datetime = Field(default_factory=datetime.now, description="Real-world creation time")

