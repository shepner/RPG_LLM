"""Container orchestrator for being instances."""

import docker
from typing import Optional, Dict, Any
from .models import BeingRegistry, ContainerStatus


class ContainerOrchestrator:
    """Orchestrates Docker containers for being instances."""
    
    def __init__(self):
        """Initialize orchestrator."""
        self.docker_client = docker.from_env()
    
    async def create_container(
        self,
        being_id: str,
        image: str = "rpg_llm_being:latest",
        environment: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Create a Docker container for a being.
        
        Args:
            being_id: Being ID
            image: Docker image to use
            environment: Environment variables
            
        Returns:
            Container ID if successful, None otherwise
        """
        try:
            container = self.docker_client.containers.create(
                image=image,
                name=f"being_{being_id}",
                environment=environment or {},
                detach=True
            )
            return container.id
        except Exception as e:
            print(f"Error creating container: {e}")
            return None
    
    async def start_container(self, container_id: str) -> bool:
        """Start a container."""
        try:
            container = self.docker_client.containers.get(container_id)
            container.start()
            return True
        except Exception as e:
            print(f"Error starting container: {e}")
            return False
    
    async def stop_container(self, container_id: str) -> bool:
        """Stop a container."""
        try:
            container = self.docker_client.containers.get(container_id)
            container.stop()
            return True
        except Exception as e:
            print(f"Error stopping container: {e}")
            return False
    
    async def delete_container(self, container_id: str) -> bool:
        """Delete a container."""
        try:
            container = self.docker_client.containers.get(container_id)
            container.remove(force=True)
            return True
        except Exception as e:
            print(f"Error deleting container: {e}")
            return False
    
    async def get_container_status(self, container_id: str) -> Optional[ContainerStatus]:
        """Get container status."""
        try:
            container = self.docker_client.containers.get(container_id)
            status = container.status
            if status == "running":
                return ContainerStatus.RUNNING
            elif status == "created":
                return ContainerStatus.CREATED
            elif status == "exited":
                return ContainerStatus.STOPPED
            else:
                return ContainerStatus.ERROR
        except Exception:
            return None

