"""Game master engine for narrative generation."""

import os
from typing import Optional, Dict, Any
from shared.llm_provider.gemini import GeminiProvider
from shared.cache.redis_cache import RedisCache
from .models import Narrative


class GMEngine:
    """Game master narrative generation engine."""
    
    def __init__(self):
        """Initialize GM engine."""
        self.llm_provider = GeminiProvider(
            api_key=os.getenv("GEMINI_API_KEY"),
            model=os.getenv("LLM_MODEL", "gemini-pro")
        )
        self.cache = RedisCache(
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379")
        )
    
    async def generate_narrative(
        self,
        context: str,
        game_time: float,
        scene_id: Optional[str] = None
    ) -> Narrative:
        """Generate narrative based on context."""
        import uuid
        
        # Check cache first
        cache_key = f"narrative:{context[:50]}"
        cached = await self.cache.get(cache_key)
        if cached:
            return Narrative(**cached)
        
        # Generate narrative
        prompt = f"Generate narrative for this game context: {context}"
        response = await self.llm_provider.generate(prompt)
        
        narrative = Narrative(
            narrative_id=str(uuid.uuid4()),
            text=response.text,
            scene_id=scene_id,
            game_time=game_time,
            metadata={}
        )
        
        # Cache result
        await self.cache.set(cache_key, narrative.dict(), ttl=3600)
        
        return narrative
    
    async def stream_narrative(
        self,
        context: str,
        game_time: float
    ):
        """Stream narrative generation."""
        prompt = f"Generate narrative for this game context: {context}"
        async for chunk in self.llm_provider.stream(prompt):
            yield chunk

