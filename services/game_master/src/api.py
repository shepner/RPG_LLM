"""Game master service API."""

import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Body
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from .gm_engine import GMEngine
from .models import Narrative
from shared.websocket.manager import WebSocketManager

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

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI(title="Game Master Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

gm_engine = GMEngine()
ws_manager = WebSocketManager()


@app.post("/narrate", response_model=Narrative)
async def narrate(
    context: str, 
    game_time: float, 
    scene_id: str = None,
    token_data: Optional[TokenData] = Depends(get_current_user) if AUTH_AVAILABLE else None
):
    """Generate narrative."""
    try:
        logger.info(f"Generating narrative for scene {scene_id} at game time {game_time}")
        narrative = await gm_engine.generate_narrative(context, game_time, scene_id)
        logger.info(f"Narrative generated: {narrative.narrative_id}")
        
        # Broadcast narrative to WebSocket subscribers
        await ws_manager.broadcast({
            "type": "narrative",
            "narrative": narrative.dict()
        }, "narrative")
        
        return narrative
    except Exception as e:
        logger.error(f"Error generating narrative: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate narrative")


@app.post("/narrate/stream")
async def narrate_stream(context: str, game_time: float):
    """Stream narrative generation."""
    async def generate():
        async for chunk in gm_engine.stream_narrative(context, game_time):
            yield f"data: {chunk.text}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time narrative updates."""
    await ws_manager.connect(websocket, "narrative")
    try:
        while True:
            data = await websocket.receive_text()
            await ws_manager.send_personal_message(
                {"type": "echo", "message": data},
                websocket
            )
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "narrative")
        logger.info("WebSocket disconnected")


class QueryRequest(BaseModel):
    """Request model for querying the game master."""
    query: str
    context: Optional[Dict[str, Any]] = None


@app.post("/query")
async def query_game_master(
    request: QueryRequest,
    token_data: Optional[TokenData] = Depends(require_gm) if AUTH_AVAILABLE else None
):
    """
    Query the Game Master (Thoth) with a question (GM only).
    
    This allows GMs to test if the game master understands narrative generation
    and can answer questions about story, scenes, and narrative.
    """
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=403, detail="GM role required to query game master")
    
    if not gm_engine.llm_provider:
        return {
            "service": "Thoth (Game Master)",
            "query": request.query,
            "response": "LLM provider not available. Cannot process queries.",
            "error": "LLM not configured"
        }
    
    prompt = f"""You are Thoth, the Game Master for a Tabletop Role-Playing Game. Your role is to generate compelling narratives, manage story flow, and create immersive experiences.

GM QUERY:
{request.query}

ADDITIONAL CONTEXT:
{request.context or "None"}

Answer the GM's question about narrative, story, scenes, or game master responsibilities. Be helpful and provide insights into how you would handle the situation."""
    
    try:
        response = await gm_engine.llm_provider.generate(
            prompt=prompt,
            system_prompt="You are Thoth, the Game Master. You create compelling narratives and manage story flow. Answer GM questions about narrative and storytelling.",
            temperature=0.7,
            max_tokens=1000
        )
        
        return {
            "service": "Thoth (Game Master)",
            "query": request.query,
            "response": response.text,
            "metadata": {
                "context_provided": request.context is not None
            }
        }
    except Exception as e:
        error_msg = str(e)
        if "/Users/" in error_msg:
            error_msg = error_msg.replace("/Users/shepner/", "/app/")
        return {
            "service": "Thoth (Game Master)",
            "query": request.query,
            "response": None,
            "error": f"Error processing query: {error_msg}"
        }


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}

