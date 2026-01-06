"""Rules engine service models."""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel


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

