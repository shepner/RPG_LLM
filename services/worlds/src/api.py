"""Worlds service API."""

import os
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from .world_state import WorldStateManager
from .models import WorldEvent
from shared.embedding_provider.gemini import GeminiEmbeddingProvider
from shared.websocket.manager import WebSocketManager

# Import auth middleware (optional - service can work without it)
try:
    import sys
    sys.path.insert(0, '/app/services/auth/src')
    from middleware import require_auth, get_current_user, TokenData
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    # Create dummy functions if auth not available
    def require_auth():
        return None
    def get_current_user():
        return None
    TokenData = None

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI(title="Worlds Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket manager for real-time updates
ws_manager = WebSocketManager()

# Initialize embedding provider
embedding_provider = GeminiEmbeddingProvider(
    api_key=os.getenv("GEMINI_API_KEY")
)

world_manager = WorldStateManager(
    database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./RPG_LLM_DATA/databases/worlds.db"),
    chroma_path=os.getenv("CHROMA_DB_PATH", "./RPG_LLM_DATA/vector_stores/worlds"),
    embedding_provider=embedding_provider
)


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    try:
        logger.info("Initializing worlds service database...")
        await world_manager.init_db()
        logger.info("Worlds service database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise


@app.post("/events", response_model=WorldEvent)
async def record_event(
    event_type: str,
    description: str,
    game_time: float,
    metadata: dict = None
):
    """Record a new event."""
    logger.info(f"Recording event: {event_type} at game time {game_time}")
    try:
        event = await world_manager.record_event(
            event_type=event_type,
            description=description,
            game_time=game_time,
            metadata=metadata
        )
        logger.info(f"Event recorded: {event.event_id}")
        
        # Broadcast event to WebSocket subscribers
        await ws_manager.broadcast({
            "type": "world_event",
            "event": event.dict()
        }, "worlds")
        
        return event
    except Exception as e:
        logger.error(f"Error recording event: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to record event")


@app.post("/history/search")
async def search_history(query: str, n_results: int = 10):
    """Search historical events."""
    try:
        logger.info(f"Searching history: {query[:50]}...")
        results = await world_manager.search_events(query, n_results)
        result_count = len(results.get('ids', [[]])[0]) if results.get('ids') and len(results.get('ids', [[]])[0]) > 0 else 0
        logger.info(f"Found {result_count} results")
        return results
    except Exception as e:
        logger.error(f"Error searching history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search history")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time world updates."""
    await ws_manager.connect(websocket, "worlds")
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            # Echo back or process message
            await ws_manager.send_personal_message(
                {"type": "echo", "message": data},
                websocket
            )
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "worlds")
        logger.info("WebSocket disconnected")


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}

