"""Anthropic Claude LLM provider implementation."""

from typing import AsyncIterator, Optional, Dict, Any, List
import anthropic
from .base import BaseLLMProvider, LLMResponse, LLMStreamChunk


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude LLM provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-opus-20240229", **kwargs):
        """
        Initialize Anthropic provider.
        
        Args:
            api_key: Anthropic API key
            model: Model name (claude-3-opus-20240229, claude-3-sonnet-20240229, etc.)
            **kwargs: Additional configuration
        """
        super().__init__(api_key, model, **kwargs)
        
        if not api_key:
            raise ValueError("Anthropic API key is required")
        
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a response from Anthropic."""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or 1024,
            temperature=temperature,
            system=system_prompt if system_prompt else "",
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )
        
        return LLMResponse(
            text=response.content[0].text,
            model=self.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            finish_reason=response.stop_reason,
            metadata={}
        )
    
    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[LLMStreamChunk]:
        """Stream a response from Anthropic."""
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens or 1024,
            temperature=temperature,
            system=system_prompt if system_prompt else "",
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        ) as stream:
            async for text in stream.text_stream:
                yield LLMStreamChunk(
                    text=text,
                    done=False,
                    metadata={}
                )
        
        yield LLMStreamChunk(text="", done=True, metadata={})
    
    async def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> List[LLMResponse]:
        """Generate responses for multiple prompts."""
        import asyncio
        
        tasks = [
            self.generate(prompt, system_prompt, temperature, max_tokens, **kwargs)
            for prompt in prompts
        ]
        
        return await asyncio.gather(*tasks)

