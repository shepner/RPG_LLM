"""Being registry service models."""

from typing import Dict, Any, Optional
from pydantic import BaseModel
from enum import Enum


class ContainerStatus(str, Enum):
    """Container status."""
    
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class BeingRegistry(BaseModel):
    """Being registry entry."""
    
    being_id: str
    container_id: Optional[str] = None
    container_status: ContainerStatus = ContainerStatus.CREATED
    service_endpoint: Optional[str] = None
    owner_id: str
    session_id: Optional[str] = None

