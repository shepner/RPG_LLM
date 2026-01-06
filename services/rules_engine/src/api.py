"""Rules engine service API."""

import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from .rule_resolver import RuleResolver
from .models import RollResult, Resolution

# Import auth middleware (optional)
try:
    import sys
    sys.path.insert(0, '/app/services/auth/src')
    from middleware import require_auth, get_current_user, TokenData
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    def require_auth():
        return None
    def get_current_user():
        return None
    TokenData = None

app = FastAPI(title="Rules Engine Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

resolver = RuleResolver()


@app.post("/roll", response_model=RollResult)
async def roll_dice(dice: str):
    """Roll dice."""
    try:
        result = resolver.roll_dice(dice)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/resolve", response_model=Resolution)
async def resolve_action(action: str, context: dict = None):
    """Resolve an action using rules."""
    # TODO: Load rules and implement full resolution
    result = resolver.resolve_action(action, {}, context)
    return result


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}

