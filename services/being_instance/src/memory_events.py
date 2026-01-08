"""Memory event models for comprehensive being memory tracking."""

from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class MemoryEventType(str, Enum):
    """Types of memory events."""
    
    # Incoming events (things sent TO the being)
    INCOMING_MESSAGE = "incoming_message"  # Message from user/other being
    INCOMING_PROMPT = "incoming_prompt"  # System prompt or GM instruction
    INCOMING_COMMAND = "incoming_command"  # Command or action request
    INCOMING_EVENT = "incoming_event"  # Game event affecting the being
    
    # Outgoing events (things the being GENERATED)
    OUTGOING_RESPONSE = "outgoing_response"  # Response to a message
    OUTGOING_THOUGHT = "outgoing_thought"  # Internal thought (private)
    OUTGOING_ACTION = "outgoing_action"  # Action taken by the being
    OUTGOING_DECISION = "outgoing_decision"  # Decision made
    
    # State changes (things done TO the being)
    STATE_CHANGE = "state_change"  # Status, health, location changes
    EFFECT_APPLIED = "effect_applied"  # Buff, debuff, spell, etc.
    MODIFICATION = "modification"  # Character modification (stats, skills, etc.)
    
    # Behavioral observations
    OBSERVED_BEHAVIOR = "observed_behavior"  # What others see (outward)
    INTERNAL_STATE = "internal_state"  # Internal state (private thoughts/feelings)


class MemoryVisibility(str, Enum):
    """Visibility of memory events."""
    
    PUBLIC = "public"  # Visible to others (outward behavior)
    PRIVATE = "private"  # Only visible to the being (internal thoughts)
    GM_ONLY = "gm_only"  # Only visible to GM


class MemoryEvent(BaseModel):
    """Comprehensive memory event model."""
    
    event_id: str
    being_id: str
    event_type: MemoryEventType
    visibility: MemoryVisibility = MemoryVisibility.PUBLIC
    
    # Content
    content: str  # The actual text/content of the event
    summary: Optional[str] = None  # Optional summary for quick reference
    
    # Context
    timestamp: datetime = Field(default_factory=datetime.now)
    game_time: Optional[float] = None  # In-game time if applicable
    session_id: Optional[str] = None
    game_system: Optional[str] = None
    
    # Relationships
    source_being_id: Optional[str] = None  # Who/what caused this event
    target_being_id: Optional[str] = None  # Who/what this event targets
    related_event_ids: List[str] = Field(default_factory=list)  # Related events
    
    # Event-specific metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Examples of metadata fields:
    # - For actions: {"action_type": "move", "location": "tavern", "success": True}
    # - For thoughts: {"emotion": "curious", "priority": "high"}
    # - For state changes: {"stat": "health", "old_value": 100, "new_value": 85}
    # - For effects: {"effect_type": "spell", "duration": 3600, "caster": "wizard_123"}


class MemoryEventCreate(BaseModel):
    """Create memory event request."""
    
    event_type: MemoryEventType
    visibility: MemoryVisibility = MemoryVisibility.PUBLIC
    content: str
    summary: Optional[str] = None
    game_time: Optional[float] = None
    session_id: Optional[str] = None
    game_system: Optional[str] = None
    source_being_id: Optional[str] = None
    target_being_id: Optional[str] = None
    related_event_ids: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
