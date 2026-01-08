"""Being service API."""

import os
import logging
from typing import Dict, Optional, List, Any
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
    being_id: Optional[str] = None  # Optional: specific being to query (stores conversation in memory)
    target_being_id: Optional[str] = None  # Optional: if set, this is a being-to-being conversation
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None  # For session-scoped prompts
    game_system: Optional[str] = None  # For game system filtering


@app.post("/query")
async def query_being_service(
    request: QueryRequest,
    token_data: Optional[TokenData] = Depends(lambda: require_auth() if AUTH_AVAILABLE else None) if AUTH_AVAILABLE else None
):
    """
    Query the Being service (Atman) with a question.
    
    If being_id is provided, the conversation is stored in that being's memory.
    Players can query beings they own or are assigned to.
    """
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=403, detail="Authentication required to query being service")
    
    # If being_id is provided, verify access and use that being's agent
    agent = None
    memory_manager = None
    
    if request.being_id:
        # #region agent log
        import json
        import time
        log_path = os.getenv("DEBUG_LOG_PATH", "/Users/shepner/RPG_LLM/.cursor/debug.log")
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    "location": "being/api.py:query_being_service",
                    "message": "Processing query for being",
                    "data": {"being_id": request.being_id, "query": request.query[:50]},
                    "timestamp": time.time() * 1000,
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A"
                }) + "\n")
        except Exception:
            pass
        # #endregion
        
        if AUTH_AVAILABLE:
            # Verify user has access to this being (owner or assigned)
            try:
                # Use require_being_access directly (already imported)
                await require_being_access(request.being_id)(None, None)
                # #region agent log
                try:
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({
                            "location": "being/api.py:query_being_service",
                            "message": "Access check passed",
                            "data": {"being_id": request.being_id},
                            "timestamp": time.time() * 1000,
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "A"
                        }) + "\n")
                except Exception:
                    pass
                # #endregion
            except HTTPException as e:
                # #region agent log
                try:
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({
                            "location": "being/api.py:query_being_service",
                            "message": "Access check failed",
                            "data": {"being_id": request.being_id, "error": str(e)},
                            "timestamp": time.time() * 1000,
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "A"
                        }) + "\n")
                except Exception:
                    pass
                # #endregion
                raise
            except Exception as e:
                logger.error(f"Error checking being access: {e}")
                # #region agent log
                try:
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({
                            "location": "being/api.py:query_being_service",
                            "message": "Access check exception",
                            "data": {"being_id": request.being_id, "error": str(e)},
                            "timestamp": time.time() * 1000,
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "A"
                        }) + "\n")
                except Exception:
                    pass
                # #endregion
                raise HTTPException(status_code=403, detail="You do not have access to this being")
        
        agent = get_agent(request.being_id)
        memory_manager = get_memory_manager(request.being_id)
        
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    "location": "being/api.py:query_being_service",
                    "message": "Agent and memory manager retrieved",
                    "data": {"being_id": request.being_id, "has_llm": agent.llm_provider is not None},
                    "timestamp": time.time() * 1000,
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A"
                }) + "\n")
        except Exception:
            pass
        # #endregion
    else:
        # Use a generic agent for query purposes (not tied to a specific being)
        agent = BeingAgent("query-temp")
        memory_manager = None
    
    if not agent.llm_provider:
        return {
            "service": "Atman (Being Service)",
            "query": request.query,
            "response": "LLM provider not available. Cannot process queries.",
            "error": "LLM not configured"
        }
    
    try:
        # Check if user is GM
        user_is_gm = token_data.role == "gm" if token_data and hasattr(token_data, 'role') else False
        
        # Load active system prompts
        active_prompts = await prompt_manager.get_active_prompts(
            session_id=request.session_id,
            game_system=request.game_system,
            user_is_gm=user_is_gm
        )
        
        # Parse @mentions in the query
        import re
        import httpx
        mention_pattern = r'@(\w+)'
        mentions = re.findall(mention_pattern, request.query)
        
        # If @mentions are found and we have a session_id, try to resolve them to being_ids
        # This allows users to use @name notation instead of being_id
        target_being_id = request.target_being_id
        if mentions and request.session_id and not target_being_id:
            # Try to resolve first mention to a being_id via being_registry
            try:
                being_registry_url = os.getenv("BEING_REGISTRY_URL", "http://localhost:8007")
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Get token for auth if available
                    auth_header = {}
                    if token_data and hasattr(token_data, 'access_token'):
                        auth_header = {"Authorization": f"Bearer {token_data.access_token}"}
                    elif token_data:
                        # Try to get token from request context
                        pass
                    
                    response = await client.get(
                        f"{being_registry_url}/beings/vicinity/{request.session_id}",
                        headers=auth_header
                    )
                    if response.status_code == 200:
                        vicinity_data = response.json()
                        beings = vicinity_data.get("beings", [])
                        # Try to match first mention to a being name
                        first_mention = mentions[0].lower()
                        for being in beings:
                            being_name = being.get("name", "").lower()
                            if first_mention in being_name or being_name.startswith(first_mention):
                                target_being_id = being.get("being_id")
                                logger.info(f"Resolved @{mentions[0]} to being_id {target_being_id}")
                                break
            except Exception as e:
                logger.warning(f"Could not resolve @mention to being_id: {e}")
                # Continue without resolving - mentions will be stored in metadata
        
        # If target_being_id is provided, this is a being-to-being conversation
        if target_being_id:
            # Verify access to target being
            if AUTH_AVAILABLE:
                try:
                    await require_being_access(request.target_being_id)(None, None)
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Error checking target being access: {e}")
                    raise HTTPException(status_code=403, detail="You do not have access to the target being")
            
            target_agent = get_agent(request.target_being_id)
            target_memory = get_memory_manager(request.target_being_id)
            
            # This is a being-to-being conversation
            # The source being (being_id) is talking to the target being (target_being_id)
            base_system_prompt = f"You are {request.target_being_id}, a thinking being in a Tabletop Role-Playing Game. Another being ({request.being_id}) is speaking to you. Respond naturally based on your character's personality, goals, and current situation."
        else:
            # Regular query (human to being or GM query)
            base_system_prompt = "You are Atman, the Being Service. You represent individual consciousness and autonomous decision-making for thinking beings in a Tabletop Role-Playing Game. Answer questions about consciousness, decision-making, and autonomous behavior."
        
        if active_prompts:
            system_prompt = f"{base_system_prompt}\n\n## Additional Context and Instructions\n{active_prompts}"
        else:
            system_prompt = base_system_prompt
        
        # Build prompt based on conversation type
        if target_being_id:
            # Being-to-being conversation
            prompt = f"""Another being ({request.being_id}) is speaking to you:

{request.query}

ADDITIONAL CONTEXT:
{request.context or "None"}

Respond naturally as your character would. Consider your personality, goals, relationships, and current situation."""
            # Use target being's agent for response
            response_agent = target_agent
        else:
            # Regular query
            prompt = f"""QUERY:
{request.query}

ADDITIONAL CONTEXT:
{request.context or "None"}

Answer the question about consciousness, decision-making, autonomous behavior, or being service responsibilities. Be helpful and provide insights."""
            response_agent = agent
        
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    "location": "being/api.py:query_being_service",
                    "message": "Calling LLM provider",
                    "data": {"being_id": request.being_id, "prompt_length": len(prompt)},
                    "timestamp": time.time() * 1000,
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A"
                }) + "\n")
        except Exception:
            pass
        # #endregion
        
        response = await response_agent.llm_provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=1000
        )
        
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    "location": "being/api.py:query_being_service",
                    "message": "LLM response received",
                    "data": {"being_id": request.being_id, "response_length": len(response.text) if response else 0},
                    "timestamp": time.time() * 1000,
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A"
                }) + "\n")
        except Exception:
            pass
        # #endregion
        
        # Store conversation in memory
        if target_being_id:
            # Being-to-being conversation: store in both beings' memories
            conversation_text_source = f"To {target_being_id}: {request.query}\nFrom {target_being_id}: {response.text}"
            conversation_text_target = f"From {request.being_id}: {request.query}\nTo {request.being_id}: {response.text}"
            
            if request.being_id and memory_manager:
                await memory_manager.add_memory(
                    conversation_text_source,
                    metadata={
                        "type": "being_conversation",
                        "target_being_id": target_being_id,
                        "session_id": request.session_id,
                        "game_system": request.game_system,
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            if target_memory:
                await target_memory.add_memory(
                    conversation_text_target,
                    metadata={
                        "type": "being_conversation",
                        "source_being_id": request.being_id,
                        "session_id": request.session_id,
                        "game_system": request.game_system,
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            logger.info(f"Stored being-to-being conversation between {request.being_id} and {target_being_id}")
        elif request.being_id and memory_manager:
            # Human-to-being conversation: store in being's memory
            conversation_text = f"User: {request.query}\nBeing: {response.text}"
            await memory_manager.add_memory(
                conversation_text,
                metadata={
                    "type": "conversation",
                    "session_id": request.session_id,
                    "game_system": request.game_system,
                    "mentions": mentions if mentions else [],
                    "timestamp": datetime.now().isoformat()
                }
            )
            logger.info(f"Stored conversation in memory for being {request.being_id}")
        
        return {
            "service": "Atman (Being Service)",
            "query": request.query,
            "response": response.text,
            "being_id": request.being_id,
            "target_being_id": target_being_id,
            "mentions": mentions,
            "metadata": {
                "context_provided": request.context is not None,
                "stored_in_memory": request.being_id is not None,
                "being_to_being": target_being_id is not None
            }
        }
    except Exception as e:
        # #region agent log
        import json
        import time
        log_path = os.getenv("DEBUG_LOG_PATH", "/Users/shepner/RPG_LLM/.cursor/debug.log")
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    "location": "being/api.py:query_being_service",
                    "message": "Exception in query",
                    "data": {"being_id": request.being_id if request else None, "error": str(e), "error_type": type(e).__name__},
                    "timestamp": time.time() * 1000,
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A"
                }) + "\n")
        except Exception:
            pass
        # #endregion
        
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
    user_is_gm = token_data.role == "gm" if token_data and hasattr(token_data, 'role') else False
    prompts = await prompt_manager.list_prompts(
        session_id=session_id,
        game_system=game_system,
        include_global=include_global,
        user_is_gm=user_is_gm
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

