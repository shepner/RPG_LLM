"""Being service API."""

import os
import logging
from typing import Dict
from fastapi import FastAPI, HTTPException
from .being_agent import BeingAgent
from .memory import MemoryManager
from .models import Thought, BeingAction

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI(title="Being Service")

# Store agents and memory managers per being
_agents: Dict[str, BeingAgent] = {}
_memory_managers: Dict[str, MemoryManager] = {}


def get_agent(being_id: str) -> BeingAgent:
    """Get or create being agent."""
    if being_id not in _agents:
        _agents[being_id] = BeingAgent(being_id)
    return _agents[being_id]


def get_memory_manager(being_id: str) -> MemoryManager:
    """Get or create memory manager."""
    if being_id not in _memory_managers:
        chroma_path = os.getenv("CHROMA_DB_PATH", "./RPG_LLM_DATA/vector_stores/beings")
        _memory_managers[being_id] = MemoryManager(being_id, chroma_path)
    return _memory_managers[being_id]


@app.post("/think", response_model=Thought)
async def think(being_id: str, context: str, game_time: float):
    """Generate thoughts."""
    try:
        logger.info(f"Generating thoughts for being {being_id}")
        agent = get_agent(being_id)
        thought = await agent.think(context, game_time)
        logger.info(f"Thought generated: {thought.thought_id}")
        return thought
    except Exception as e:
        logger.error(f"Error generating thoughts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate thoughts")


@app.post("/decide", response_model=BeingAction)
async def decide(being_id: str, context: str, game_time: float):
    """Make a decision."""
    try:
        logger.info(f"Making decision for being {being_id}")
        agent = get_agent(being_id)
        action = await agent.decide(context, game_time)
        logger.info(f"Decision made: {action.action_id}")
        return action
    except Exception as e:
        logger.error(f"Error making decision: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to make decision")


@app.post("/memory/add")
async def add_memory(being_id: str, content: str, metadata: dict = None):
    """Add a memory."""
    memory_manager = get_memory_manager(being_id)
    await memory_manager.add_memory(content, metadata)
    return {"message": "Memory added"}


@app.post("/memory/search")
async def search_memory(being_id: str, query: str, n_results: int = 10):
    """Search memories."""
    memory_manager = get_memory_manager(being_id)
    results = await memory_manager.search_memories(query, n_results)
    return results


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}

