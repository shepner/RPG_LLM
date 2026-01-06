"""Being registry service API."""

from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .registry import Registry
from .models import BeingRegistry
from .character_creator import CharacterCreator

# Import auth middleware (optional)
try:
    import sys
    sys.path.insert(0, '/app/services/auth/src')
    from middleware import require_auth, require_gm, get_current_user, TokenData
    AUTH_AVAILABLE = True
except ImportError:
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
    
    # TODO: Query actual characters from registry
    # For now, return empty list
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


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}

