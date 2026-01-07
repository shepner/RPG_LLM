"""Being registry service API."""

from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .registry import Registry
from .models import BeingRegistry
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
    name: str
    backstory: Optional[str] = None
    personality: Optional[str] = None
    appearance: Optional[str] = None
    game_system: Optional[str] = None
    session_id: Optional[str] = None
    automatic: bool = False  # If True, auto-generate everything


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
    
    # Get characters from Auth service
    try:
        import httpx
        auth_url = os.getenv("AUTH_URL", "http://localhost:8000")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{auth_url}/beings/assigned",
                headers={"Authorization": f"Bearer {token_data.access_token if token_data else ''}"}
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
    except Exception as e:
        logger.error(f"Error fetching user characters: {e}")
    
    return {"characters": []}


@app.post("/beings/create")
async def create_character(
    request: CharacterCreateRequest,
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
        
        # Register the being
        global registry
        if registry is None:
            registry = get_registry()
        registry_entry = registry.register_being(being_id, owner_id, request.session_id)
        
        return {
            "being_id": being_id,
            "registry": registry_entry,
            "character_data": character_data,
            "message": "Character created successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create character: {str(e)}")


@app.get("/beings/{being_id}", response_model=BeingRegistry)
async def get_being(being_id: str):
    """Get being registry entry."""
    global registry
    if registry is None:
        registry = get_registry()
    entry = registry.get_being(being_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Being not found")
    return entry


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

