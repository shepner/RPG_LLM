"""Game master service models."""

from typing import Optional, Dict, Any
from pydantic import BaseModel


class Narrative(BaseModel):
    """Narrative model."""
    
    narrative_id: str
    text: str
    scene_id: Optional[str] = None
    game_time: float
    metadata: Dict[str, Any] = {}

