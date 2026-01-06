"""Game master service API."""

import logging
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from .gm_engine import GMEngine
from .models import Narrative

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI(title="Game Master Service")

gm_engine = GMEngine()


@app.post("/narrate", response_model=Narrative)
async def narrate(context: str, game_time: float, scene_id: str = None):
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


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}

