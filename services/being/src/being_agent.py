"""Being agent for decision-making."""

import os
from typing import Optional, Dict, Any
from shared.llm_provider.gemini import GeminiProvider
from shared.cache.redis_cache import RedisCache
from .models import Thought, BeingAction


class BeingAgent:
    """Agent for being decision-making."""
    
    def __init__(self, being_id: str):
        """Initialize being agent."""
        import logging
        logger = logging.getLogger(__name__)
        
        self.being_id = being_id
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logger.warning(f"GEMINI_API_KEY not set for being {being_id}. LLM provider will not be available.")
                self.llm_provider = None
            else:
                self.llm_provider = GeminiProvider(
                    api_key=api_key,
                    model=os.getenv("LLM_MODEL", "gemini-2.5-flash")
                )
                logger.info(f"LLM provider initialized for being {being_id}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM provider for being {being_id}: {e}", exc_info=True)
            self.llm_provider = None
        
        try:
            self.cache = RedisCache(
                redis_url=os.getenv("REDIS_URL", "redis://localhost:6379")
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Redis cache for being {being_id}: {e}")
            self.cache = None
    
    async def think(self, context: str, game_time: float, system_prompt: Optional[str] = None) -> Thought:
        """Generate thoughts."""
        import uuid
        
        prompt = f"As this being, think about: {context}"
        base_system = "You are a thinking being in a Tabletop Role-Playing Game. Generate thoughts that reflect your character's personality, goals, and current situation."
        system = system_prompt if system_prompt else base_system
        response = await self.llm_provider.generate(prompt, system_prompt=system)
        
        return Thought(
            thought_id=str(uuid.uuid4()),
            being_id=self.being_id,
            text=response.text,
            game_time=game_time,
            metadata={}
        )
    
    async def decide(self, context: str, game_time: float, system_prompt: Optional[str] = None) -> BeingAction:
        """Make a decision and generate action."""
        import uuid
        
        prompt = f"As this being, decide what to do: {context}"
        base_system = "You are a thinking being in a Tabletop Role-Playing Game. Make decisions that reflect your character's personality, goals, motivations, and current situation."
        system = system_prompt if system_prompt else base_system
        response = await self.llm_provider.generate(prompt, system_prompt=system)
        
        return BeingAction(
            action_id=str(uuid.uuid4()),
            being_id=self.being_id,
            action_type="general",
            description=response.text,
            game_time=game_time,
            metadata={}
        )

