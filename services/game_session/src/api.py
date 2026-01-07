"""Game session service API."""

import os
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware

from .session_manager import SessionManager
from .models import GameSession, SessionCreate, SessionState, SessionStatus

app = FastAPI(title="Game Session Service")

# Add CORS middleware to allow web interface to access this service
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081", "http://127.0.0.1:8081", "*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

session_manager = SessionManager(
    database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./RPG_LLM_DATA/databases/game_session.db")
)


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    await session_manager.init_db()


@app.post("/sessions", response_model=GameSession)
async def create_session(session_data: SessionCreate, gm_user_id: str):
    """Create a new game session."""
    session = await session_manager.create_session(
        name=session_data.name,
        gm_user_id=gm_user_id,
        description=session_data.description,
        game_system_type=session_data.game_system_type,
        time_mode_preference=session_data.time_mode_preference,
        settings=session_data.settings
    )
    return session


@app.get("/sessions", response_model=List[GameSession])
async def list_sessions(
    user_id: Optional[str] = None,
    status: Optional[str] = None
):
    """List game sessions, optionally filtered by user or status."""
    from .models import SessionStatus
    
    session_status = None
    if status:
        try:
            session_status = SessionStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    sessions = await session_manager.list_sessions(user_id, session_status)
    return sessions


@app.get("/sessions/{session_id}", response_model=GameSession)
async def get_session(session_id: str):
    """Get session details."""
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.post("/sessions/{session_id}/join")
async def join_session(session_id: str, user_id: str):
    """Join a game session."""
    success = await session_manager.join_session(session_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Joined session"}


@app.post("/sessions/{session_id}/leave")
async def leave_session(session_id: str, user_id: str):
    """Leave a game session."""
    success = await session_manager.leave_session(session_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Left session"}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str, gm_user_id: str):
    """Delete a game session (GM only - must be the session's GM)."""
    from .middleware import require_auth, TokenData
    from fastapi import Depends
    
    # Get session to verify GM ownership
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Only the GM of the session can delete it
    if session.gm_user_id != gm_user_id:
        raise HTTPException(status_code=403, detail="Only the session's Game Master can delete it")
    
    success = await session_manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete session")
    return {"message": "Session deleted successfully"}


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}

