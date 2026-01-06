"""Base LLM provider interface."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Dict, Any, List
from pydantic import BaseModel


class LLMResponse(BaseModel):
    """LLM response model."""
    
    text: str
    model: str
    usage: Optional[Dict[str, int]] = None  # tokens, prompt_tokens, completion_tokens
    finish_reason: Optional[str] = None
    metadata: Dict[str, Any] = {}


class LLMStreamChunk(BaseModel):
    """LLM streaming response chunk."""
    
    text: str
    done: bool = False
    metadata: Dict[str, Any] = {}


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "default", **kwargs):
        """
        Initialize LLM provider.
        
        Args:
            api_key: API key for the provider
            model: Model name to use
            **kwargs: Additional provider-specific configuration
        """
        self.api_key = api_key
        self.model = model
        self.config = kwargs
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse object
        """
        pass
    
    @abstractmethod
    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[LLMStreamChunk]:
        """
        Stream a response from the LLM.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
            
        Yields:
            LLMStreamChunk objects
        """
        pass
    
    @abstractmethod
    async def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> List[LLMResponse]:
        """
        Generate responses for multiple prompts (batch processing).
        
        Args:
            prompts: List of user prompts
            system_prompt: Optional system prompt (applied to all)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
            
        Returns:
            List of LLMResponse objects
        """
        pass

