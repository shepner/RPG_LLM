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
    
    async def think(self, context: str, game_time: float, system_prompt: Optional[str] = None, memory_manager=None) -> Thought:
        """
        Generate thoughts (internal, private to the being).
        
        Args:
            context: Context for thinking
            game_time: Game time
            system_prompt: Optional system prompt
            memory_manager: Optional memory manager to store the thought
        """
        import uuid
        
        prompt = f"As this being, think about: {context}"
        base_system = "You are a thinking being in a Tabletop Role-Playing Game. Generate thoughts that reflect your character's personality, goals, and current situation."
        system = system_prompt if system_prompt else base_system
        response = await self.llm_provider.generate(prompt, system_prompt=system)
        
        thought = Thought(
            thought_id=str(uuid.uuid4()),
            being_id=self.being_id,
            text=response.text,
            game_time=game_time,
            metadata={}
        )
        
        # Store thought in memory as private event
        if memory_manager:
            await memory_manager.add_thought(
                content=thought.text,
                game_time=game_time,
                metadata={"thought_id": thought.thought_id, "context": context}
            )
        
        return thought
    
    async def decide(self, context: str, game_time: float, system_prompt: Optional[str] = None, memory_manager=None) -> BeingAction:
        """
        Make a decision and generate action.
        
        Args:
            context: Context for decision
            game_time: Game time
            system_prompt: Optional system prompt
            memory_manager: Optional memory manager to store the action
        """
        import uuid
        
        prompt = f"As this being, decide what to do: {context}"
        base_system = "You are a thinking being in a Tabletop Role-Playing Game. Make decisions that reflect your character's personality, goals, motivations, and current situation."
        system = system_prompt if system_prompt else base_system
        response = await self.llm_provider.generate(prompt, system_prompt=system)
        
        action = BeingAction(
            action_id=str(uuid.uuid4()),
            being_id=self.being_id,
            action_type="general",
            description=response.text,
            game_time=game_time,
            metadata={}
        )
        
        # Store action in memory as public event
        if memory_manager:
            await memory_manager.add_action(
                content=action.description,
                action_type=action.action_type,
                game_time=game_time,
                metadata={"action_id": action.action_id, "context": context, **action.metadata}
            )
        
        return action

