"""Google Gemini LLM provider implementation."""

import os
from typing import AsyncIterator, Optional, Dict, Any, List
import google.generativeai as genai
from .base import BaseLLMProvider, LLMResponse, LLMStreamChunk


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-pro", **kwargs):
        """
        Initialize Gemini provider.
        
        Args:
            api_key: Gemini API key (or use GOOGLE_APPLICATION_CREDENTIALS)
            model: Model name (gemini-pro, gemini-pro-vision, etc.)
            **kwargs: Additional configuration
        """
        super().__init__(api_key, model, **kwargs)
        
        # Configure Gemini
        if api_key:
            genai.configure(api_key=api_key)
        elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            # Use service account
            genai.configure()
        else:
            raise ValueError("Either api_key or GOOGLE_APPLICATION_CREDENTIALS must be provided")
        
        self.client = genai.GenerativeModel(model)
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a response from Gemini."""
        import asyncio
        
        # Combine system prompt and user prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        # Configure generation parameters
        generation_config = {
            "temperature": temperature,
            **kwargs
        }
        if max_tokens:
            generation_config["max_output_tokens"] = max_tokens
        
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(**generation_config)
            )
        )
        
        return LLMResponse(
            text=response.text,
            model=self.model,
            usage={
                "prompt_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else None,
                "completion_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else None,
                "total_tokens": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else None,
            },
            finish_reason=response.candidates[0].finish_reason.name if response.candidates else None,
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
        """Stream a response from Gemini."""
        import asyncio
        
        # Combine system prompt and user prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        # Configure generation parameters
        generation_config = {
            "temperature": temperature,
            **kwargs
        }
        if max_tokens:
            generation_config["max_output_tokens"] = max_tokens
        
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        response_stream = await loop.run_in_executor(
            None,
            lambda: self.client.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(**generation_config),
                stream=True
            )
        )
        
        for chunk in response_stream:
            if chunk.text:
                yield LLMStreamChunk(
                    text=chunk.text,
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
        
        # Process prompts concurrently
        tasks = [
            self.generate(prompt, system_prompt, temperature, max_tokens, **kwargs)
            for prompt in prompts
        ]
        
        return await asyncio.gather(*tasks)

