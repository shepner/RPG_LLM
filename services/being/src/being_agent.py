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
        self.being_id = being_id
        self.llm_provider = GeminiProvider(
            api_key=os.getenv("GEMINI_API_KEY"),
            model=os.getenv("LLM_MODEL", "gemini-2.5-flash")
        )
        self.cache = RedisCache(
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379")
        )
    
    async def think(self, context: str, game_time: float) -> Thought:
        """Generate thoughts."""
        import uuid
        
        prompt = f"As this being, think about: {context}"
        response = await self.llm_provider.generate(prompt)
        
        return Thought(
            thought_id=str(uuid.uuid4()),
            being_id=self.being_id,
            text=response.text,
            game_time=game_time,
            metadata={}
        )
    
    async def decide(self, context: str, game_time: float) -> BeingAction:
        """Make a decision and generate action."""
        import uuid
        
        prompt = f"As this being, decide what to do: {context}"
        response = await self.llm_provider.generate(prompt)
        
        return BeingAction(
            action_id=str(uuid.uuid4()),
            being_id=self.being_id,
            action_type="general",
            description=response.text,
            game_time=game_time,
            metadata={}
        )

