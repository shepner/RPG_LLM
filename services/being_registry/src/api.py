"""Being registry service API."""

from typing import Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from .registry import Registry
from .models import BeingRegistry

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

registry = Registry()


@app.post("/beings/register", response_model=BeingRegistry)
async def register_being(being_id: str, owner_id: str, session_id: str = None):
    """Register a being."""
    entry = registry.register_being(being_id, owner_id, session_id)
    return entry


@app.get("/beings/{being_id}", response_model=BeingRegistry)
async def get_being(being_id: str):
    """Get being registry entry."""
    entry = registry.get_being(being_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Being not found")
    return entry


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}

