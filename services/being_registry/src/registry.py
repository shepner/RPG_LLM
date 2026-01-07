"""Being registry for container management."""

import os
import docker
from typing import Dict, Optional, List
from .models import BeingRegistry, ContainerStatus


class Registry:
    """Manages being container registry."""
    
    def __init__(self, use_docker: bool = True):
        """Initialize registry."""
        self._registry: Dict[str, BeingRegistry] = {}
        if use_docker:
            try:
                self.docker_client = docker.from_env()
            except Exception:
                # Docker not available, continue without it
                self.docker_client = None
        else:
            self.docker_client = None
    
    def register_being(
        self,
        being_id: str,
        owner_id: str,
        session_id: Optional[str] = None
    ) -> BeingRegistry:
        """Register a being."""
        registry_entry = BeingRegistry(
            being_id=being_id,
            owner_id=owner_id,
            session_id=session_id,
            container_status=ContainerStatus.CREATED
        )
        self._registry[being_id] = registry_entry
        return registry_entry
    
    def get_being(self, being_id: str) -> Optional[BeingRegistry]:
        """Get being registry entry."""
        return self._registry.get(being_id)
    
    def get_beings_by_session(self, session_id: str) -> List[BeingRegistry]:
        """Get all beings in a session."""
        return [entry for entry in self._registry.values() if entry.session_id == session_id]
    
    def get_entry(self, being_id: str) -> Optional[Dict[str, Any]]:
        """Get being registry entry as dict."""
        entry = self._registry.get(being_id)
        if entry:
            return {
                "being_id": entry.being_id,
                "name": getattr(entry, 'name', f"Character {being_id[:8]}"),
                "owner_id": entry.owner_id,
                "session_id": entry.session_id
            }
        return None
    
    def update_status(
        self,
        being_id: str,
        status: ContainerStatus,
        container_id: Optional[str] = None
    ):
        """Update container status."""
        if being_id in self._registry:
            self._registry[being_id].container_status = status
            if container_id:
                self._registry[being_id].container_id = container_id

