"""Being registry service API."""

from fastapi import FastAPI, HTTPException
from .registry import Registry
from .models import BeingRegistry

app = FastAPI(title="Being Registry Service")

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

