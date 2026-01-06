"""Time management service API."""

import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from .time_engine import TimeEngine
from .models import GameTime, HistoricalEvent

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

app = FastAPI(title="Time Management Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

time_engine = TimeEngine(
    database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./RPG_LLM_DATA/databases/time_management.db")
)


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    await time_engine.init_db()


@app.get("/time", response_model=GameTime)
async def get_time(session_id: str):
    """Get current game time."""
    game_time = await time_engine.get_current_time(session_id)
    if not game_time:
        raise HTTPException(status_code=404, detail="Session not found")
    return game_time


@app.post("/time/advance")
async def advance_time(session_id: str, amount: float):
    """Advance game time."""
    await time_engine.advance_time(session_id, amount)
    return {"message": "Time advanced"}


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}

