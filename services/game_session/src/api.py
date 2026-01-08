"""Game session service API."""

import os
import sys
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .session_manager import SessionManager
from .models import GameSession, SessionCreate, SessionUpdate, SessionState, SessionStatus

# Import WebSocket manager
sys.path.insert(0, '/app/shared/websocket')
from manager import WebSocketManager

app = FastAPI(title="Game Session Service")

# Initialize WebSocket manager for session updates
ws_manager = WebSocketManager()

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
    # Broadcast session update via WebSocket
    await ws_manager.broadcast({
        "type": "session_updated",
        "action": "created",
        "session": session.model_dump()
    })
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
    
    # Get updated session and broadcast
    updated_session = await session_manager.get_session(session_id)
    if updated_session:
        await ws_manager.broadcast({
            "type": "session_updated",
            "action": "updated",
            "session": updated_session.model_dump()
        })
    
    return {"message": "Joined session"}


@app.post("/sessions/{session_id}/leave")
async def leave_session(session_id: str, user_id: str):
    """Leave a game session."""
    success = await session_manager.leave_session(session_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get updated session
    updated_session = await session_manager.get_session(session_id)
    if updated_session:
        # Broadcast session update via WebSocket
        await ws_manager.broadcast({
            "type": "session_updated",
            "action": "updated",
            "session": updated_session.model_dump()
        })
    
    return {"message": "Left session"}


@app.put("/sessions/{session_id}")
async def update_session(
    session_id: str,
    session_data: SessionUpdate,
    gm_user_id: str = Query(...)
):
    """Update a game session (GM only - must be the session's GM)."""
    # Get session to verify GM ownership
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Only the GM of the session can update it
    if session.gm_user_id != gm_user_id:
        raise HTTPException(status_code=403, detail="Only the session's Game Master can update it")
    
    updated_session = await session_manager.update_session(session_id, session_data)
    if not updated_session:
        raise HTTPException(status_code=500, detail="Failed to update session")
    
    # Broadcast session update via WebSocket
    await ws_manager.broadcast({
        "type": "session_updated",
        "action": "updated",
        "session": updated_session.model_dump()
    })
    return updated_session


@app.post("/sessions/{session_id}/players/{user_id}")
async def add_player_to_session(
    session_id: str,
    user_id: str,
    gm_user_id: str = Query(...)
):
    """Add a player to a session (GM only)."""
    # Get session to verify GM ownership
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Only the GM of the session can add players
    if session.gm_user_id != gm_user_id:
        raise HTTPException(status_code=403, detail="Only the session's Game Master can add players")
    
    # Don't allow adding the GM as a player
    if user_id == session.gm_user_id:
        raise HTTPException(status_code=400, detail="Cannot add the Game Master as a player")
    
    success = await session_manager.join_session(session_id, user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add player to session")
    
    # Get updated session and broadcast
    updated_session = await session_manager.get_session(session_id)
    if updated_session:
        await ws_manager.broadcast({
            "type": "session_updated",
            "action": "updated",
            "session": updated_session.model_dump()
        })
    
    return {"message": "Player added to session"}


@app.delete("/sessions/{session_id}/players/{user_id}")
async def remove_player_from_session(
    session_id: str,
    user_id: str,
    gm_user_id: str = Query(...)
):
    """Remove a player from a session (GM only)."""
    # Get session to verify GM ownership
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Only the GM of the session can remove players
    if session.gm_user_id != gm_user_id:
        raise HTTPException(status_code=403, detail="Only the session's Game Master can remove players")
    
    success = await session_manager.leave_session(session_id, user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to remove player from session")
    
    # Get updated session and broadcast
    updated_session = await session_manager.get_session(session_id)
    if updated_session:
        await ws_manager.broadcast({
            "type": "session_updated",
            "action": "updated",
            "session": updated_session.model_dump()
        })
    
    return {"message": "Player removed from session"}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str, gm_user_id: str = Query(...)):
    """Delete a game session (GM only - must be the session's GM)."""
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
    
    # Broadcast session deletion via WebSocket
    await ws_manager.broadcast({
        "type": "session_updated",
        "action": "deleted",
        "session_id": session_id
    })
    return {"message": "Session deleted successfully"}


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}

