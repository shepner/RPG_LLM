"""Being service models."""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from shared.models.common import BeingState


class Thought(BaseModel):
    """Thought model."""
    
    thought_id: str
    being_id: str
    text: str
    game_time: float
    metadata: Dict[str, Any] = {}


class BeingAction(BaseModel):
    """Being action model."""
    
    action_id: str
    being_id: str
    action_type: str
    description: str
    game_time: float
    thoughts: Optional[str] = None
    metadata: Dict[str, Any] = {}

