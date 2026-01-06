"""Time management service API."""

import os
from fastapi import FastAPI, HTTPException
from .time_engine import TimeEngine
from .models import GameTime, HistoricalEvent

app = FastAPI(title="Time Management Service")

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

