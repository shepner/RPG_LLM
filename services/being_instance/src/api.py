"""Being instance service API - single being in isolated container."""

import os
import logging
from datetime import datetime
from typing import Dict, Optional, List, Any
from fastapi import FastAPI, HTTPException, Depends, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .being_agent import BeingAgent
from .memory import MemoryManager
from .models import Thought, BeingAction
from .prompt_manager import PromptManager
from .memory_events import MemoryEventCreate, MemoryEventType, MemoryVisibility

# Import auth middleware (optional)
try:
    import sys
    sys.path.insert(0, '/app/services/auth/src')
    from middleware import require_auth, TokenData
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    def require_auth():
        return None
    TokenData = None

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI(title="Being Instance Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get being_id from environment (set by orchestrator)
BEING_ID = os.getenv("BEING_ID")
if not BEING_ID:
    raise ValueError("BEING_ID environment variable must be set for being instance service")

logger.info(f"Being instance service initialized for being_id: {BEING_ID}")

# Initialize isolated storage for this being
DATABASE_PATH = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///./RPG_LLM_DATA/databases/being_{BEING_ID}.db")
VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH", f"./RPG_LLM_DATA/vector_stores/being_{BEING_ID}")

# Initialize components for this single being
agent = BeingAgent(BEING_ID)
memory_manager = MemoryManager(BEING_ID, VECTOR_STORE_PATH)
prompt_manager = PromptManager(DATABASE_PATH, "being")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    await prompt_manager.init_db()
    logger.info(f"Being instance {BEING_ID} ready")


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "healthy",
        "being_id": BEING_ID,
        "service": "being_instance"
    }


@app.get("/info")
async def get_being_info(
    token_data: Optional[TokenData] = Depends(lambda: require_auth() if AUTH_AVAILABLE else None) if AUTH_AVAILABLE else None
):
    """Get being information."""
    # Try to get character data from being_registry
    try:
        import httpx
        being_registry_url = os.getenv("BEING_REGISTRY_URL", "http://localhost:8007")
        async with httpx.AsyncClient(timeout=5.0) as client:
            auth_header = {}
            if token_data and hasattr(token_data, 'access_token'):
                auth_header = {"Authorization": f"Bearer {token_data.access_token}"}
            
            registry_response = await client.get(
                f"{being_registry_url}/beings/{BEING_ID}",
                headers=auth_header
            )
            
            if registry_response.status_code == 200:
                registry_entry = registry_response.json()
                return {
                    "being_id": BEING_ID,
                    "name": registry_entry.get("name") or f"Character {BEING_ID[:8]}",
                    "owner_id": registry_entry.get("owner_id"),
                    "session_id": registry_entry.get("session_id"),
                    "container_status": registry_entry.get("container_status"),
                    "service_endpoint": registry_entry.get("service_endpoint")
                }
    except Exception as e:
        logger.warning(f"Could not fetch character data from registry: {e}")
    
    return {
        "being_id": BEING_ID,
        "name": f"Character {BEING_ID[:8]}",
        "status": "running"
    }


class QueryRequest(BaseModel):
    """Query request model."""
    query: str
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    game_system: Optional[str] = None
    source_user_id: Optional[str] = None  # User/being who sent the query


@app.post("/query")
async def query_being(
    request: QueryRequest,
    http_request: Request,
    token_data: Optional[TokenData] = Depends(lambda: require_auth() if AUTH_AVAILABLE else None) if AUTH_AVAILABLE else None
):
    """
    Query this being instance.
    
    This is the main endpoint for interacting with the being.
    All queries are stored in the being's isolated memory.
    """
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=403, detail="Authentication required")
    
    if not agent.llm_provider:
        error_msg = "LLM provider not available. Please configure GEMINI_API_KEY environment variable."
        logger.error(f"LLM provider not available for being {BEING_ID}. {error_msg}")
        return {
            "service": "Being Instance",
            "query": request.query,
            "response": error_msg,
            "error": "LLM not configured",
            "being_id": BEING_ID
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
        
        # Get character-specific system prompt
        async def get_character_system_prompt() -> str:
            """Get character-specific system prompt from being_registry."""
            try:
                import httpx
                being_registry_url = os.getenv("BEING_REGISTRY_URL", "http://localhost:8007")
                async with httpx.AsyncClient(timeout=5.0) as client:
                    auth_header = {}
                    if http_request:
                        auth_header_value = http_request.headers.get("Authorization")
                        if auth_header_value:
                            auth_header = {"Authorization": auth_header_value}
                    
                    registry_response = await client.get(
                        f"{being_registry_url}/beings/{BEING_ID}",
                        headers=auth_header
                    )
                    
                    if registry_response.status_code == 200:
                        registry_entry = registry_response.json()
                        character_name = registry_entry.get("name")
                        
                        # If no name, this is a new character in conversational creation mode
                        if not character_name:
                            return """You are a new character being created in a Tabletop Role-Playing Game. You are helping your creator define who you are through conversation. 

Start by asking for the character's name. Then ask about:
- Backstory and history
- Personality traits
- Appearance
- Goals and motivations

Be friendly, curious, and help guide the creation process. Once you have the name, you should introduce yourself using that name in your responses."""
                        else:
                            return f"""You are {character_name}, a unique thinking being in a Tabletop Role-Playing Game. 

You have your own personality, goals, memories, and experiences. Respond naturally as this character would, based on your individual traits and the context of the conversation.

Remember:
- You are an autonomous being with your own consciousness
- You have your own memories and experiences stored in your memory
- You should respond in character, reflecting your unique personality and perspective
- You are not a generic service - you are {character_name}, a distinct individual"""
                    else:
                        logger.warning(f"Could not fetch character data for {BEING_ID}: {registry_response.status_code}")
            except Exception as e:
                logger.warning(f"Error fetching character data for {BEING_ID}: {e}")
            
            # Fallback to generic prompt
            return f"You are a thinking being (ID: {BEING_ID}) in a Tabletop Role-Playing Game. Respond naturally based on your character's personality, goals, and current situation."
        
        base_system_prompt = await get_character_system_prompt()
        
        if active_prompts:
            system_prompt = f"{base_system_prompt}\n\n## Additional Context and Instructions\n{active_prompts}"
        else:
            system_prompt = base_system_prompt
        
        # Build prompt
        prompt = f"""QUERY:
{request.query}

ADDITIONAL CONTEXT:
{request.context or "None"}

Respond naturally as your character would. Consider your personality, goals, relationships, and current situation."""
        
        logger.info(f"Calling LLM for being {BEING_ID}, prompt length: {len(prompt)}, system prompt length: {len(system_prompt)}")
        response = await agent.llm_provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=1000
        )
        
        logger.info(f"LLM response received for being {BEING_ID}, response type: {type(response)}, has text: {hasattr(response, 'text') if response else False}")
        
        # Validate response
        if not response:
            logger.error("LLM provider returned None response")
            raise ValueError("LLM provider returned None response")
        
        if not hasattr(response, 'text') or response.text is None:
            logger.error(f"LLM response has no text attribute or text is None. Response object: {response}, attributes: {dir(response)}")
            raise ValueError("LLM response has no text attribute")
        
        response_text = response.text.strip() if response.text else ""
        
        logger.info(f"LLM response text length for being {BEING_ID}: {len(response_text)}")
        
        if not response_text:
            logger.warning(f"LLM returned empty response for being {BEING_ID}. Response object: {response}")
            response_text = "I'm sorry, I didn't receive a response. Please try again."
        
        # Check if character provided their name in the response or user's query
        # If we don't have a name yet and the user provided one, update the registry
        try:
            import httpx
            being_registry_url = os.getenv("BEING_REGISTRY_URL", "http://localhost:8007")
            async with httpx.AsyncClient(timeout=5.0) as client:
                auth_header = {}
                if http_request:
                    auth_header_value = http_request.headers.get("Authorization")
                    if auth_header_value:
                        auth_header = {"Authorization": auth_header_value}
                
                # Check current name
                registry_check = await client.get(
                    f"{being_registry_url}/beings/{BEING_ID}",
                    headers=auth_header
                )
                
                if registry_check.status_code == 200:
                    registry_entry = registry_check.json()
                    current_name = registry_entry.get("name")
                    
                    # If no name yet, try to extract from response or query
                    if not current_name:
                        import re
                        # Look for patterns like "My name is X" or "I'm X" or "Call me X" or just "X" as first word
                        name_patterns = [
                            r"(?:my name is|i'm|i am|call me|name's|name is|i go by)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)",
                            r"^([A-Z][a-zA-Z]+)(?:\s+here|$)",  # "Aura" or "Aura here"
                            r"^([A-Z][a-zA-Z]+)(?:\s+is my name|$)",  # "Aura is my name"
                        ]
                        
                        extracted_name = None
                        # First check user's query
                        for pattern in name_patterns:
                            match = re.search(pattern, request.query, re.IGNORECASE)
                            if match:
                                extracted_name = match.group(1).strip()
                                break
                        
                        # Then check character's response
                        if not extracted_name:
                            for pattern in name_patterns:
                                match = re.search(pattern, response_text, re.IGNORECASE)
                                if match:
                                    extracted_name = match.group(1).strip()
                                    break
                        
                        # If we found a name, update the registry
                        if extracted_name and len(extracted_name) < 50:  # Sanity check
                            update_response = await client.put(
                                f"{being_registry_url}/beings/{BEING_ID}/name",
                                json={"name": extracted_name},
                                headers=auth_header
                            )
                            if update_response.status_code == 200:
                                logger.info(f"Updated being name to: {extracted_name}")
        except Exception as e:
            logger.warning(f"Could not check/update being name: {e}")
        
        # Store comprehensive memory events
        source_type = "user"
        if token_data and hasattr(token_data, 'role') and token_data.role == "gm":
            source_type = "gm"
        
        # Store incoming message
        await memory_manager.add_incoming_message(
            content=request.query,
            source_being_id=None,  # Human user or other being (passed via source_user_id if needed)
            session_id=request.session_id,
            game_system=request.game_system,
            metadata={
                "source_type": source_type,
                "source_user_id": request.source_user_id or (token_data.user_id if token_data else None),
                "context": request.context
            }
        )
        
        # Store outgoing response
        await memory_manager.add_outgoing_response(
            content=response_text,
            target_being_id=None,  # Response to human
            session_id=request.session_id,
            game_system=request.game_system,
            metadata={"conversation_type": "human_to_being"}
        )
        
        logger.info(f"Stored conversation events for being {BEING_ID}")
        
        return {
            "service": "Being Instance",
            "query": request.query,
            "response": response_text,
            "being_id": BEING_ID,
            "metadata": {
                "context_provided": request.context is not None,
                "stored_in_memory": True
            }
        }
    except Exception as e:
        error_msg = str(e)
        if "/Users/" in error_msg:
            # Sanitize local paths from error messages
            import re
            error_msg = re.sub(r'/Users/[^/]+/', '/app/', error_msg)
        logger.error(f"Error processing query for being {BEING_ID}: {error_msg}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {error_msg}")


@app.post("/think")
async def think(
    context: str,
    game_time: float = 0.0,
    token_data: Optional[TokenData] = Depends(lambda: require_auth() if AUTH_AVAILABLE else None) if AUTH_AVAILABLE else None
):
    """Generate thoughts (internal, private to the being)."""
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=403, detail="Authentication required")
    
    thought = await agent.think(context, game_time, memory_manager=memory_manager)
    return thought


@app.post("/decide")
async def decide(
    context: str,
    game_time: float = 0.0,
    token_data: Optional[TokenData] = Depends(lambda: require_auth() if AUTH_AVAILABLE else None) if AUTH_AVAILABLE else None
):
    """Make a decision and generate action."""
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=403, detail="Authentication required")
    
    action = await agent.decide(context, game_time, memory_manager=memory_manager)
    return action


@app.post("/memory/event")
async def add_memory_event(
    event: MemoryEventCreate,
    token_data: Optional[TokenData] = Depends(lambda: require_auth() if AUTH_AVAILABLE else None) if AUTH_AVAILABLE else None
):
    """Add a memory event."""
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=403, detail="Authentication required")
    
    memory_event = await memory_manager.add_event(event)
    return memory_event


@app.post("/memory/search")
async def search_memory(
    query: str,
    n_results: int = 10,
    event_types: Optional[List[str]] = None,
    include_private: bool = True,
    token_data: Optional[TokenData] = Depends(lambda: require_auth() if AUTH_AVAILABLE else None) if AUTH_AVAILABLE else None
):
    """Search memories."""
    if AUTH_AVAILABLE and not token_data:
        raise HTTPException(status_code=403, detail="Authentication required")
    
    # Convert string event types to enum if provided
    event_type_enums = None
    if event_types:
        from .memory_events import MemoryEventType
        event_type_enums = [MemoryEventType(et) for et in event_types if et in [e.value for e in MemoryEventType]]
    
    results = await memory_manager.search_memories(
        query=query,
        n_results=n_results,
        event_types=event_type_enums,
        include_private=include_private
    )
    return results
