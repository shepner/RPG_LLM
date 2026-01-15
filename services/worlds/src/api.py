"""Worlds service API."""

import os
import logging
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .world_state import WorldStateManager
from .models import WorldEvent, SystemPrompt, SystemPromptCreate, SystemPromptUpdate
from shared.embedding_provider.gemini import GeminiEmbeddingProvider
from shared.llm_provider.gemini import GeminiProvider
from shared.websocket.manager import WebSocketManager
from .prompt_manager import PromptManager

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

# Initialize LLM provider
llm_provider = GeminiProvider(
    api_key=os.getenv("GEMINI_API_KEY"),
    model=os.getenv("LLM_MODEL", "gemini-2.5-flash")
)

world_manager = WorldStateManager(
    database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./RPG_LLM_DATA/databases/worlds.db"),
    chroma_path=os.getenv("CHROMA_DB_PATH", "./RPG_LLM_DATA/vector_stores/worlds"),
    embedding_provider=embedding_provider
)

# Initialize database for system prompts
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./RPG_LLM_DATA/databases/worlds.db")
prompt_manager = PromptManager(DATABASE_URL, "worlds")


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    try:
        logger.info("Initializing worlds service database...")
        await world_manager.init_db()
        await prompt_manager.init_db()
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


class QueryRequest(BaseModel):
    """Request model for querying the worlds service."""
    query: str
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None  # For session-scoped prompts
    game_system: Optional[str] = None  # For game system filtering


@app.post("/query")
async def query_worlds_service(
    request: QueryRequest,
    token_data: Optional[TokenData] = Depends(lambda: require_auth() if AUTH_AVAILABLE else None) if AUTH_AVAILABLE else None
):
    """
    Query the Worlds service (Gaia) with a question (GM only).
    
    This allows GMs to test if the worlds service understands world state,
    logical consistency, physics validation, and world evolution.
    """
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=403, detail="Authentication required to query worlds service")
    
    if not llm_provider:
        return {
            "service": "Gaia (Worlds Service)",
            "query": request.query,
            "response": "LLM provider not available. Cannot process queries.",
            "error": "LLM not configured"
        }
    
    try:
        # Load active system prompts
        active_prompts = await prompt_manager.get_active_prompts(
            session_id=request.session_id,
            game_system=request.game_system
        )
        
        # Search for relevant world events to provide context
        relevant_events = []
        if world_manager:
            try:
                search_results = await world_manager.search_events(request.query, n_results=5)
                if search_results and search_results.get('documents') and len(search_results['documents']) > 0:
                    relevant_events = search_results['documents'][0][:5]  # Get top 5
            except Exception as e:
                logger.warning(f"Error searching world events for context: {e}")
        
        # Combine base system prompt with active prompts
        base_system_prompt = "You are Gaia, the Worlds Service. You manage world state, track events, validate logical consistency, and oversee world evolution in a Tabletop Role-Playing Game. Answer GM questions about world state, physics, logical consistency, and world evolution."
        if active_prompts:
            system_prompt = f"{base_system_prompt}\n\n## Additional Context and Instructions\n{active_prompts}"
        else:
            system_prompt = base_system_prompt
        
        # Build context from relevant events
        events_context = ""
        if relevant_events:
            events_context = "\n\n## Relevant World Events:\n" + "\n".join([f"- {event}" for event in relevant_events[:5]])
        
        prompt = f"""You are Gaia, the Worlds Service for a Tabletop Role-Playing Game. Your role is to manage world state, validate logical consistency, oversee physics, and track world evolution.

GM QUERY:
{request.query}

ADDITIONAL CONTEXT:
{request.context or "None"}
{events_context}

Answer the GM's question about world state, logical consistency, physics validation, world evolution, or world service responsibilities. Be helpful and provide insights into how you would handle the situation."""
        
        # Gaia should be neutral by default (not especially deterministic nor creative).
        gaia_temperature = float(os.getenv("GAIA_TEMPERATURE", "0.7"))
        if isinstance(request.context, dict) and request.context.get("llm_temperature") is not None:
            try:
                gaia_temperature = float(request.context.get("llm_temperature"))
            except Exception:
                pass
        response = await llm_provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=gaia_temperature,
            max_tokens=1000
        )
        
        return {
            "service": "Gaia (Worlds Service)",
            "query": request.query,
            "response": response.text,
            "metadata": {
                "context_provided": request.context is not None,
                "events_found": len(relevant_events)
            }
        }
    except Exception as e:
        error_msg = str(e)
        if "/Users/" in error_msg:
            error_msg = error_msg.replace("/Users/shepner/", "/app/")
        return {
            "service": "Gaia (Worlds Service)",
            "query": request.query,
            "response": None,
            "error": f"Error processing query: {error_msg}"
        }


# System Prompt Management Endpoints (GM only)
@app.post("/prompts", response_model=SystemPrompt)
async def create_prompt(
    prompt_data: SystemPromptCreate,
    token_data: Optional[TokenData] = Depends(lambda: require_auth() if AUTH_AVAILABLE else None) if AUTH_AVAILABLE else None
):
    """Create a new system prompt."""
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=403, detail="Authentication required")
    prompt = await prompt_manager.create_prompt(prompt_data)
    return prompt


@app.get("/prompts", response_model=List[SystemPrompt])
async def list_prompts(
    session_id: Optional[str] = None,
    game_system: Optional[str] = None,
    include_global: bool = True,
    token_data: Optional[TokenData] = Depends(lambda: require_auth() if AUTH_AVAILABLE else None) if AUTH_AVAILABLE else None
):
    """List system prompts."""
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=403, detail="Authentication required")
    prompts = await prompt_manager.list_prompts(
        session_id=session_id,
        game_system=game_system,
        include_global=include_global
    )
    return prompts


@app.get("/prompts/{prompt_id}", response_model=SystemPrompt)
async def get_prompt(
    prompt_id: str,
    token_data: Optional[TokenData] = Depends(lambda: require_auth() if AUTH_AVAILABLE else None) if AUTH_AVAILABLE else None
):
    """Get a system prompt by ID."""
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=403, detail="Authentication required")
    prompt = await prompt_manager.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt


@app.patch("/prompts/{prompt_id}", response_model=SystemPrompt)
async def update_prompt(
    prompt_id: str,
    prompt_data: SystemPromptUpdate,
    token_data: Optional[TokenData] = Depends(lambda: require_auth() if AUTH_AVAILABLE else None) if AUTH_AVAILABLE else None
):
    """Update a system prompt."""
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=403, detail="Authentication required")
    prompt = await prompt_manager.update_prompt(prompt_id, prompt_data)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt


@app.delete("/prompts/{prompt_id}")
async def delete_prompt(
    prompt_id: str,
    token_data: Optional[TokenData] = Depends(lambda: require_auth() if AUTH_AVAILABLE else None) if AUTH_AVAILABLE else None
):
    """Delete a system prompt."""
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=403, detail="Authentication required")
    success = await prompt_manager.delete_prompt(prompt_id)
    if not success:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"message": "Prompt deleted successfully"}

