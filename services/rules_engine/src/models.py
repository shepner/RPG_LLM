"""Rules engine service models."""

from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class Rule(BaseModel):
    """Rule model."""
    
    rule_id: str
    name: str
    category: str
    description: str
    content: str
    metadata: Dict[str, Any] = {}


class RollResult(BaseModel):
    """Dice roll result."""
    
    dice: str  # e.g., "1d20+5"
    result: int
    rolls: List[int] = []
    modifier: int = 0


class Resolution(BaseModel):
    """Rule resolution result."""
    
    rule_id: Optional[str] = None
    result: Any
    explanation: str
    metadata: Dict[str, Any] = {}


class PromptScope(str, Enum):
    """System prompt scope."""
    
    GLOBAL = "global"  # Applies to all sessions
    SESSION = "session"  # Applies to specific session(s)


class SystemPrompt(BaseModel):
    """System prompt/context model."""
    
    prompt_id: str
    service_name: str  # "rules_engine", "game_master", "being"
    title: str
    content: str
    scope: PromptScope = PromptScope.GLOBAL
    session_ids: List[str] = Field(default_factory=list)  # Empty for global, populated for session-scoped
    game_system: Optional[str] = None  # Optional: tag with game system (D&D, Pathfinder, etc.)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SystemPromptCreate(BaseModel):
    """Create system prompt request."""
    
    title: str
    content: str
    scope: PromptScope = PromptScope.GLOBAL
    session_ids: List[str] = Field(default_factory=list)
    game_system: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SystemPromptUpdate(BaseModel):
    """Update system prompt request."""
    
    title: Optional[str] = None
    content: Optional[str] = None
    scope: Optional[PromptScope] = None
    session_ids: Optional[List[str]] = None
    game_system: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

