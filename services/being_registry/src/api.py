"""Being registry service API."""

import os
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .registry import Registry
from .models import BeingRegistry, ContainerStatus
from .character_creator import CharacterCreator
from .system_validator import SystemValidator

# Import auth middleware (optional)
try:
    import sys
    import os
    # Add auth service to path
    auth_src_path = '/app/services/auth/src'
    if os.path.exists(auth_src_path):
        sys.path.insert(0, auth_src_path)
        # Also add parent directory so relative imports work
        sys.path.insert(0, '/app/services/auth')
    
    # Import with absolute path to avoid relative import issues
    import importlib.util
    middleware_path = os.path.join(auth_src_path, 'middleware.py')
    if os.path.exists(middleware_path):
        spec = importlib.util.spec_from_file_location("auth_middleware", middleware_path)
        auth_middleware = importlib.util.module_from_spec(spec)
        # Set up the module's __package__ to help with relative imports
        auth_middleware.__package__ = 'src'
        sys.modules['auth_middleware'] = auth_middleware
        spec.loader.exec_module(auth_middleware)
        
        from auth_middleware import require_auth, require_gm, get_current_user, TokenData
        AUTH_AVAILABLE = True
        import logging
        logger = logging.getLogger(__name__)
    else:
        raise ImportError(f"Middleware file not found at {middleware_path}")
except (ImportError, Exception) as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Auth middleware not available: {e}")
    AUTH_AVAILABLE = False
    def require_auth():
        return None
    def require_gm():
        return None
    def get_current_user():
        return None
    TokenData = None

app = FastAPI(title="Being Registry Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize registry lazily to avoid Docker connection errors
def get_registry():
    """Get registry instance."""
    from .registry import Registry
    try:
        return Registry(use_docker=True)
    except Exception:
        # Docker not available, use minimal registry
        return Registry(use_docker=False)

registry = None  # Will be initialized on first use
character_creator = CharacterCreator()
system_validator = SystemValidator()


class CharacterCreateRequest(BaseModel):
    """Character creation request."""
    name: Optional[str] = None  # Optional for conversational creation
    backstory: Optional[str] = None
    personality: Optional[str] = None
    appearance: Optional[str] = None
    game_system: Optional[str] = None
    session_id: Optional[str] = None
    automatic: bool = False  # If True, auto-generate everything
    conversational: bool = False  # If True, create minimal character and engage in dialog


@app.post("/beings/register", response_model=BeingRegistry)
async def register_being(being_id: str, owner_id: str, session_id: str = None):
    """Register a being."""
    global registry
    if registry is None:
        registry = get_registry()
    entry = registry.register_being(being_id, owner_id, session_id)
    return entry


@app.get("/beings/my-characters")
async def get_my_characters(
    request: Request,
    token_data: Optional[TokenData] = Depends(require_auth) if AUTH_AVAILABLE else None
):
    """Get all characters owned or assigned to the current user."""
    # Check authentication
    if AUTH_AVAILABLE:
        if not token_data:
            raise HTTPException(status_code=401, detail="Authentication required")
    else:
        # If auth is not available, allow access (for development)
        token_data = None
    
    # Get the auth token from request headers
    auth_header = request.headers.get("Authorization", "")
    
    # Get characters from Auth service
    try:
        import httpx
        auth_url = os.getenv("AUTH_URL", "http://localhost:8000")
        global registry
        if registry is None:
            registry = get_registry()
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{auth_url}/beings/assigned",
                headers={"Authorization": auth_header} if auth_header else {}
            )
            if response.status_code == 200:
                being_ids = response.json()
                # Get character details from registry
                characters = []
                for being_id in being_ids:
                    entry = registry.get_entry(being_id)
                    if entry:
                        characters.append({
                            "being_id": being_id,
                            "name": entry.get("name", f"Character {being_id[:8]}"),
                            "owner_id": entry.get("owner_id"),
                            "session_id": entry.get("session_id")
                        })
                return {"characters": characters}
            elif response.status_code == 401:
                raise HTTPException(status_code=401, detail="Authentication required")
            else:
                logger.warning(f"Auth service returned {response.status_code} for /beings/assigned")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user characters: {e}", exc_info=True)
        # Return empty list instead of failing completely
        return {"characters": []}
    
    return {"characters": []}


@app.post("/beings/create")
async def create_character(
    request: CharacterCreateRequest,
    http_request: Request = None,
    token_data: Optional[TokenData] = Depends(require_auth) if AUTH_AVAILABLE else None
):
    """Create a new character/being."""
    if not token_data:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        import uuid
        being_id = str(uuid.uuid4())
        owner_id = token_data.user_id
        
        if request.automatic:
            # Auto-generate character
            character_data = await character_creator.create_automatic(
                owner_id=owner_id,
                context={"session_id": request.session_id},
                game_system=request.game_system
            )
        else:
            # Manual creation with player-provided flavor
            flavor_data = {
                "name": request.name,
                "backstory": request.backstory,
                "personality": request.personality,
                "appearance": request.appearance
            }
            character_data = await character_creator.create_manual(
                being_id=being_id,
                owner_id=owner_id,
                flavor_data=flavor_data,
                game_system=request.game_system
            )
        
        # Get character name from character_data or request
        character_name = None
        if not request.automatic and request.name:
            character_name = request.name
        elif character_data and isinstance(character_data, dict):
            character_name = character_data.get('name')
        elif hasattr(character_data, 'name'):
            character_name = character_data.name
        
        # Register the being
        global registry
        if registry is None:
            registry = get_registry()
        registry_entry = registry.register_being(being_id, owner_id, request.session_id, name=character_name)
        
        # Create container for being instance (Phase 2: Container Orchestration)
        container_id = None
        service_endpoint = None
        container_status = ContainerStatus.CREATED
        
        try:
            from .orchestrator import ContainerOrchestrator
            orchestrator = ContainerOrchestrator()
            
            # Create container
            result = await orchestrator.create_container(being_id)
            if result:
                container_id, port = result
                service_endpoint = f"http://localhost:{port}"
                
                # Start container and wait for health
                started = await orchestrator.start_container(container_id, wait_for_health=True, timeout=30)
                if started:
                    container_status = ContainerStatus.RUNNING
                else:
                    container_status = ContainerStatus.ERROR
                    logger.warning(f"Container {container_id} started but health check failed")
                
                # Update registry with container info
                registry.update_status(being_id, container_status, container_id)
                registry_entry.container_id = container_id
                registry_entry.container_status = container_status
                registry_entry.service_endpoint = service_endpoint
                
                # Also update service_endpoint in registry
                registry.update_service_endpoint(being_id, service_endpoint)
                
                logger.info(f"Container created for being {being_id}: {container_id} on port {port}, endpoint: {service_endpoint}")
            else:
                logger.warning(f"Could not create container for being {being_id}. Continuing without container.")
        except Exception as e:
            logger.error(f"Error creating container for being {being_id}: {e}", exc_info=True)
            # Continue without container - being can still work with shared service
        
        # Create ownership record in auth service
        if AUTH_AVAILABLE:
            try:
                # Try to import auth_manager directly and create ownership
                auth_manager_path = os.path.join(auth_src_path, 'auth_manager.py')
                if os.path.exists(auth_manager_path):
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("auth_manager", auth_manager_path)
                    auth_manager_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(auth_manager_module)
                    
                    # Create auth manager instance with same config as auth service
                    auth_url = os.getenv("AUTH_URL", "http://localhost:8000")
                    auth_manager_instance = auth_manager_module.AuthManager(
                        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./RPG_LLM_DATA/databases/auth.db"),
                        jwt_secret_key=os.getenv("JWT_SECRET_KEY", "change-me-in-production"),
                        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
                        jwt_expiration_hours=int(os.getenv("JWT_EXPIRATION", "24").replace("h", ""))
                    )
                    
                    # #region agent log
                    import json
                    import time
                    log_path = os.getenv("DEBUG_LOG_PATH", "/Users/shepner/RPG_LLM/.cursor/debug.log")
                    try:
                        with open(log_path, 'a') as f:
                            f.write(json.dumps({
                                "location": "being_registry/api.py:create_character",
                                "message": "Creating ownership record",
                                "data": {"being_id": being_id, "owner_id": owner_id},
                                "timestamp": time.time() * 1000,
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "A"
                            }) + "\n")
                    except Exception:
                        pass  # Don't fail if logging fails
                    # #endregion
                    
                    await auth_manager_instance.set_being_ownership(
                        being_id=being_id,
                        owner_id=owner_id,
                        created_by=owner_id,
                        assigned_user_ids=None
                    )
                    
                    # #region agent log
                    try:
                        with open(log_path, 'a') as f:
                            f.write(json.dumps({
                                "location": "being_registry/api.py:create_character",
                                "message": "Ownership record created successfully",
                                "data": {"being_id": being_id},
                                "timestamp": time.time() * 1000,
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "A"
                            }) + "\n")
                    except Exception:
                        pass
                    # #endregion
            except Exception as e:
                # If direct import fails, log but don't fail character creation
                import logging
                import json
                logger = logging.getLogger(__name__)
                logger.warning(f"Could not create ownership record in auth service: {e}")
                
                # #region agent log
                import time
                log_path = os.getenv("DEBUG_LOG_PATH", "/Users/shepner/RPG_LLM/.cursor/debug.log")
                try:
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({
                            "location": "being_registry/api.py:create_character",
                            "message": "Failed to create ownership record",
                            "data": {"error": str(e), "being_id": being_id},
                            "timestamp": time.time() * 1000,
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "A"
                        }) + "\n")
                except Exception:
                    pass
                # #endregion
        
        return {
            "being_id": being_id,
            "registry": registry_entry,
            "character_data": character_data,
            "message": "Character created successfully",
            "conversational": request.conversational
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create character: {str(e)}")


@app.get("/beings/{being_id}", response_model=BeingRegistry)
async def get_being(
    being_id: str,
    token_data: Optional[TokenData] = Depends(require_auth) if AUTH_AVAILABLE else None
):
    """Get being registry entry."""
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    global registry
    if registry is None:
        registry = get_registry()
    entry = registry.get_being(being_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Being not found")
    return entry


@app.delete("/beings/{being_id}")
async def delete_being(
    being_id: str,
    http_request: Request,
    token_data: Optional[TokenData] = Depends(require_auth) if AUTH_AVAILABLE else None
):
    """Delete a being and its container."""
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    global registry
    if registry is None:
        registry = get_registry()
    
    # Get the being entry to check ownership
    entry = registry.get_being(being_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Being not found")
    
    # Check if user has permission to delete (owner or GM)
    if AUTH_AVAILABLE:
        is_owner = entry.owner_id == token_data.user_id
        is_gm = token_data.role == "gm" if hasattr(token_data, 'role') else False
        
        if not (is_owner or is_gm):
            raise HTTPException(status_code=403, detail="You do not have permission to delete this being")
    
    # Delete container if it exists
    if entry.container_id:
        try:
            from .orchestrator import ContainerOrchestrator
            orchestrator = ContainerOrchestrator()
            await orchestrator.delete_container(entry.container_id, force=True)
            logger.info(f"Container {entry.container_id} deleted for being {being_id}")
        except Exception as e:
            logger.error(f"Error deleting container for being {being_id}: {e}", exc_info=True)
            # Continue with deletion even if container deletion fails
    
    # Delete from registry
    deleted = registry.delete_being(being_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Being not found in registry")
    
    # Delete ownership record from auth service
    if AUTH_AVAILABLE:
        try:
            import httpx
            import logging
            logger = logging.getLogger(__name__)
            auth_url = os.getenv("AUTH_URL", "http://localhost:8000")
            
            # Get the Authorization header from the incoming request
            auth_header = http_request.headers.get("Authorization")
            if not auth_header:
                logger.warning("No Authorization header found for ownership deletion.")
            else:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    ownership_response = await client.delete(
                        f"{auth_url}/beings/{being_id}/ownership",
                        headers={"Authorization": auth_header}
                    )
                    if ownership_response.status_code not in [200, 404]:
                        # 404 is okay (ownership might not exist), but log other errors
                        logger.warning(f"Failed to delete ownership record: {ownership_response.status_code} - {ownership_response.text}")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error deleting ownership record: {e}", exc_info=True)
            # Don't fail the whole operation if ownership deletion fails
    
    return {"message": "Being deleted successfully", "being_id": being_id}


@app.get("/beings/vicinity/{session_id}")
async def get_beings_in_vicinity(
    session_id: str,
    token_data: Optional[TokenData] = Depends(require_auth) if AUTH_AVAILABLE else None
):
    """Get all beings in the same session (vicinity)."""
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    registry = get_registry()
    beings_in_session = []
    
    # Get all beings in this session from registry
    if hasattr(registry, '_registry'):
        for being_id, entry in registry._registry.items():
            if hasattr(entry, 'session_id') and entry.session_id == session_id:
                # Try to get name from registry entry or use being_id as fallback
                name = f"Character {being_id[:8]}"
                if hasattr(entry, 'name') and entry.name:
                    name = entry.name
                elif isinstance(entry, dict) and 'name' in entry:
                    name = entry['name']
                
                beings_in_session.append({
                    "being_id": being_id,
                    "name": name,
                    "owner_id": entry.owner_id if hasattr(entry, 'owner_id') else None
                })
    
    return {"beings": beings_in_session}


@app.get("/beings/list")
async def list_all_beings(
    token_data: Optional[TokenData] = Depends(require_gm) if AUTH_AVAILABLE else None
):
    """List all beings/characters (GM only)."""
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    global registry
    if registry is None:
        registry = get_registry()
    
    # Get all beings from registry
    all_beings = []
    if hasattr(registry, '_registry'):
        for being_id, entry in registry._registry.items():
            # Try to get character name from being service if available
            # For now, just return the registry entry
            all_beings.append({
                "being_id": entry.being_id,
                "owner_id": entry.owner_id,
                "session_id": entry.session_id,
                "container_status": entry.container_status.value if hasattr(entry.container_status, 'value') else str(entry.container_status),
                "name": f"Character {being_id[:8]}"  # Placeholder name
            })
    
    return {"characters": all_beings}


@app.post("/beings/{being_id}/migrate")
async def migrate_being_to_container(
    being_id: str,
    token_data: Optional[TokenData] = Depends(require_gm) if AUTH_AVAILABLE else None
):
    """
    Migrate an existing being to an isolated container (Phase 4: Migration).
    GM only.
    """
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    global registry
    if registry is None:
        registry = get_registry()
    
    # Get being entry
    entry = registry.get_being(being_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Being not found")
    
    # Check if already has container
    if entry.service_endpoint and entry.container_status == ContainerStatus.RUNNING:
        return {
            "message": f"Being {being_id} already has a running container",
            "container_id": entry.container_id,
            "service_endpoint": entry.service_endpoint
        }
    
    # Create container for this being
    try:
        from .orchestrator import ContainerOrchestrator
        orchestrator = ContainerOrchestrator()
        
        result = await orchestrator.create_container(being_id)
        if result:
            container_id, port = result
            service_endpoint = f"http://localhost:{port}"
            
            # Start container and wait for health
            started = await orchestrator.start_container(container_id, wait_for_health=True, timeout=30)
            if started:
                container_status = ContainerStatus.RUNNING
            else:
                container_status = ContainerStatus.ERROR
            
            # Update registry
            registry.update_status(being_id, container_status, container_id)
            registry.update_service_endpoint(being_id, service_endpoint)
            entry.container_id = container_id
            entry.container_status = container_status
            entry.service_endpoint = service_endpoint
            
            logger.info(f"Migrated being {being_id} to container {container_id} on port {port}")
            
            return {
                "message": f"Being {being_id} migrated to container successfully",
                "container_id": container_id,
                "service_endpoint": service_endpoint,
                "status": container_status.value
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create container")
    except Exception as e:
        logger.error(f"Error migrating being {being_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}


@app.get("/system/validate")
async def validate_system(
    token_data: Optional[TokenData] = Depends(require_gm) if AUTH_AVAILABLE else None
):
    """
    Validate system functionality (GM only).
    
    Checks:
    - All services are responding
    - Atman-Ma'at integration (Being Service ↔ Rules Engine)
    - Rules indexing status
    - Overall system health
    """
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=403, detail="GM role required to validate system")
    
    try:
        validation_report = await system_validator.validate_all()
        return validation_report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

