"""Container orchestrator for being instances."""

import os
import hashlib
import asyncio
import logging
import docker
from typing import Optional, Dict, Any, Tuple
from .models import BeingRegistry, ContainerStatus

logger = logging.getLogger(__name__)


class ContainerOrchestrator:
    """Orchestrates Docker containers for being instances."""
    
    def __init__(self):
        """Initialize orchestrator."""
        try:
            self.docker_client = docker.from_env()
            logger.info("Docker client initialized successfully")
        except Exception as e:
            # Docker may not be available in all environments
            self.docker_client = None
            logger.warning(f"Docker client initialization failed: {e}")
        
        # Port range for being instances (9000-9999)
        self.port_base = 9000
        self.port_range = 1000
        
        # Track port assignments
        self._port_assignments: Dict[str, int] = {}
    
    def _get_port_for_being(self, being_id: str) -> int:
        """
        Get a consistent port for a being based on its ID.
        Uses hash to ensure same being always gets same port.
        """
        # Hash the being_id to get a consistent port
        hash_obj = hashlib.md5(being_id.encode())
        hash_int = int(hash_obj.hexdigest(), 16)
        port = self.port_base + (hash_int % self.port_range)
        
        # If port is already assigned to a different being, find next available
        while port in self._port_assignments.values() and self._port_assignments.get(being_id) != port:
            port = (port + 1) % self.port_range + self.port_base
        
        self._port_assignments[being_id] = port
        return port
    
    def _get_container_name(self, being_id: str) -> str:
        """Get container name for a being."""
        # Docker container names must be lowercase and can't have special chars
        safe_id = being_id.replace('-', '_').lower()
        return f"rpg_llm_being_{safe_id}"
    
    async def create_container(
        self,
        being_id: str,
        image: str = "rpg_llm_being_instance:latest",
        environment: Optional[Dict[str, Any]] = None,
        volumes: Optional[Dict[str, Dict[str, str]]] = None
    ) -> Optional[Tuple[str, int]]:
        """
        Create a Docker container for a being instance.
        
        Args:
            being_id: Being ID
            image: Docker image to use (default: being_instance service)
            environment: Environment variables
            volumes: Volume mounts
            
        Returns:
            Tuple of (container_id, port) if successful, None otherwise
        """
        if not self.docker_client:
            logger.error("Docker client not available")
            return None
        
        try:
            # Get port for this being
            port = self._get_port_for_being(being_id)
            container_name = self._get_container_name(being_id)
            
            # Check if container already exists
            try:
                existing = self.docker_client.containers.get(container_name)
                logger.info(f"Container {container_name} already exists, returning existing")
                return (existing.id, port)
            except docker.errors.NotFound:
                pass
            
            # Build environment variables
            env_vars = {
                "BEING_ID": being_id,
                "PORT": "8006",  # Internal port (being_instance listens on 8006)
                "DATABASE_URL": f"sqlite+aiosqlite:///./RPG_LLM_DATA/databases/being_instance_{being_id}.db",
                "CHROMA_DB_PATH": f"./RPG_LLM_DATA/vector_stores/being_instances/{being_id}",
                "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
                "LLM_MODEL": os.getenv("LLM_MODEL", "gemini-2.5-flash"),
                "REDIS_URL": os.getenv("REDIS_URL", "redis://redis:6379"),
                "AUTH_URL": os.getenv("AUTH_URL", "http://auth:8000"),
                "BEING_REGISTRY_URL": os.getenv("BEING_REGISTRY_URL", "http://being_registry:8007"),
            }
            
            if environment:
                env_vars.update(environment)
            
            # Build volume mounts
            volume_mounts = {
                "/app/RPG_LLM_DATA": {
                    "bind": "/app/RPG_LLM_DATA",
                    "mode": "rw"
                }
            }
            
            if volumes:
                volume_mounts.update(volumes)
            
            # Create container
            logger.info(f"Creating container {container_name} for being {being_id} on port {port}")
            container = self.docker_client.containers.create(
                image=image,
                name=container_name,
                environment=env_vars,
                ports={"8006/tcp": port},  # Map internal 8006 to external port
                volumes=volume_mounts,
                detach=True,
                network_mode="bridge"  # Use bridge network to access other services
            )
            
            logger.info(f"Container {container_name} created with ID {container.id}")
            return (container.id, port)
            
        except docker.errors.ImageNotFound:
            logger.error(f"Docker image {image} not found. Please build it first.")
            return None
        except docker.errors.APIError as e:
            logger.error(f"Docker API error creating container: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creating container for being {being_id}: {e}", exc_info=True)
            return None
    
    async def start_container(self, container_id: str, wait_for_health: bool = True, timeout: int = 30) -> bool:
        """
        Start a container and optionally wait for it to be healthy.
        
        Args:
            container_id: Container ID or name
            wait_for_health: Whether to wait for health check
            timeout: Timeout in seconds for health check
            
        Returns:
            True if started (and healthy if wait_for_health), False otherwise
        """
        if not self.docker_client:
            return False
        
        try:
            container = self.docker_client.containers.get(container_id)
            
            if container.status == "running":
                logger.info(f"Container {container_id} is already running")
                return True
            
            logger.info(f"Starting container {container_id}")
            container.start()
            
            if wait_for_health:
                return await self._wait_for_health(container, timeout)
            
            return True
            
        except docker.errors.NotFound:
            logger.error(f"Container {container_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error starting container {container_id}: {e}", exc_info=True)
            return False
    
    async def _wait_for_health(self, container, timeout: int = 30) -> bool:
        """Wait for container to be healthy."""
        import httpx
        
        # Get port from container
        port = None
        try:
            ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
            if "8006/tcp" in ports:
                port_mappings = ports["8006/tcp"]
                if port_mappings:
                    port = port_mappings[0]["HostPort"]
        except Exception as e:
            logger.warning(f"Could not determine port for health check: {e}")
        
        if not port:
            logger.warning("Port not found, skipping health check")
            return True  # Assume healthy if we can't check
        
        # Wait for health endpoint
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.get(f"http://localhost:{port}/health")
                    if response.status_code == 200:
                        logger.info(f"Container {container.name} is healthy")
                        return True
            except Exception:
                pass
            
            await asyncio.sleep(1)
        
        logger.warning(f"Container {container.name} health check timed out")
        return False
    
    async def stop_container(self, container_id: str) -> bool:
        """Stop a container."""
        if not self.docker_client:
            return False
        
        try:
            container = self.docker_client.containers.get(container_id)
            if container.status == "running":
                logger.info(f"Stopping container {container_id}")
                container.stop(timeout=10)
            return True
        except docker.errors.NotFound:
            logger.warning(f"Container {container_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error stopping container {container_id}: {e}", exc_info=True)
            return False
    
    async def delete_container(self, container_id: str, force: bool = True) -> bool:
        """Delete a container."""
        if not self.docker_client:
            return False
        
        try:
            container = self.docker_client.containers.get(container_id)
            
            # Stop if running
            if container.status == "running":
                container.stop(timeout=10)
            
            # Remove container
            container.remove(force=force)
            
            # Clean up port assignment
            for bid, port in list(self._port_assignments.items()):
                if container.id == container_id or container.name == self._get_container_name(bid):
                    del self._port_assignments[bid]
            
            logger.info(f"Container {container_id} deleted")
            return True
            
        except docker.errors.NotFound:
            logger.warning(f"Container {container_id} not found")
            return True  # Already deleted
        except Exception as e:
            logger.error(f"Error deleting container {container_id}: {e}", exc_info=True)
            return False
    
    async def get_container_status(self, container_id: str) -> Optional[ContainerStatus]:
        """Get container status."""
        if not self.docker_client:
            return None
        
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
        except docker.errors.NotFound:
            return None
        except Exception as e:
            logger.error(f"Error getting container status: {e}")
            return None
    
    async def get_container_by_being_id(self, being_id: str) -> Optional[Any]:
        """Get container by being ID."""
        if not self.docker_client:
            return None
        
        try:
            container_name = self._get_container_name(being_id)
            return self.docker_client.containers.get(container_name)
        except docker.errors.NotFound:
            return None
        except Exception as e:
            logger.error(f"Error getting container for being {being_id}: {e}")
            return None
    
    def get_port_for_being(self, being_id: str) -> Optional[int]:
        """Get the port assigned to a being."""
        return self._port_assignments.get(being_id) or self._get_port_for_being(being_id)

