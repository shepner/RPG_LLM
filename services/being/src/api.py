"""Being service API."""

import os
import logging
from typing import Dict, Optional, List
from fastapi import FastAPI, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .being_agent import BeingAgent
from .memory import MemoryManager
from .models import Thought, BeingAction, SystemPrompt, SystemPromptCreate, SystemPromptUpdate
from .prompt_manager import PromptManager

# Import auth middleware (optional)
try:
    import sys
    sys.path.insert(0, '/app/services/auth/src')
    from middleware import require_auth, require_being_access, get_current_user, TokenData
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    def require_auth():
        return None
    def require_being_access(being_id: str):
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

app = FastAPI(title="Being Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store agents and memory managers per being
_agents: Dict[str, BeingAgent] = {}
_memory_managers: Dict[str, MemoryManager] = {}

# Initialize database for system prompts
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./RPG_LLM_DATA/databases/being.db")
prompt_manager = PromptManager(DATABASE_URL, "being")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    await prompt_manager.init_db()


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
async def think(
    being_id: str, 
    context: str, 
    game_time: float,
    token_data: Optional[TokenData] = Depends(lambda: require_being_access(being_id) if AUTH_AVAILABLE else None) if AUTH_AVAILABLE else None
):
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
async def decide(
    being_id: str, 
    context: str, 
    game_time: float,
    token_data: Optional[TokenData] = Depends(lambda: require_being_access(being_id) if AUTH_AVAILABLE else None) if AUTH_AVAILABLE else None
):
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


class QueryRequest(BaseModel):
    """Request model for querying the being service."""
    query: str
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None  # For session-scoped prompts
    game_system: Optional[str] = None  # For game system filtering


@app.post("/query")
async def query_being_service(
    request: QueryRequest,
    token_data: Optional[TokenData] = Depends(lambda: require_auth() if AUTH_AVAILABLE else None) if AUTH_AVAILABLE else None
):
    """
    Query the Being service (Atman) with a question (GM only).
    
    This allows GMs to test if the being service understands consciousness,
    decision-making, and autonomous behavior.
    """
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=403, detail="Authentication required to query being service")
    
    # Use a generic agent for query purposes (not tied to a specific being)
    # We'll create a temporary agent just for this query
    temp_agent = BeingAgent("query-temp")
    
    if not temp_agent.llm_provider:
        return {
            "service": "Atman (Being Service)",
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
        
        # Combine base system prompt with active prompts
        base_system_prompt = "You are Atman, the Being Service. You represent individual consciousness and autonomous decision-making for thinking beings in a Tabletop Role-Playing Game. Answer GM questions about consciousness, decision-making, and autonomous behavior."
        if active_prompts:
            system_prompt = f"{base_system_prompt}\n\n## Additional Context and Instructions\n{active_prompts}"
        else:
            system_prompt = base_system_prompt
        
        prompt = f"""You are Atman, the Being Service for a Tabletop Role-Playing Game. Your role is to manage individual consciousness, decision-making, and autonomous behavior for thinking beings.

GM QUERY:
{request.query}

ADDITIONAL CONTEXT:
{request.context or "None"}

Answer the GM's question about consciousness, decision-making, autonomous behavior, or being service responsibilities. Be helpful and provide insights into how you would handle the situation."""
        
        response = await temp_agent.llm_provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=1000
        )
        
        return {
            "service": "Atman (Being Service)",
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
            "service": "Atman (Being Service)",
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

