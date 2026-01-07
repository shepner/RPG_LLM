"""Google Gemini LLM provider implementation."""

import os
from typing import AsyncIterator, Optional, Dict, Any, List
import google.generativeai as genai
from .base import BaseLLMProvider, LLMResponse, LLMStreamChunk


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash", **kwargs):
        """
        Initialize Gemini provider.
        
        Args:
            api_key: Gemini API key (or use GOOGLE_APPLICATION_CREDENTIALS)
            model: Model name (gemini-2.5-flash (stable), gemini-3-flash-preview, gemini-3-pro-preview, etc.)
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
        
        # Normalize model name - remove 'models/' prefix if present, as GenerativeModel adds it
        normalized_model = model.replace('models/', '') if model.startswith('models/') else model
        
        # Use normalized model directly
        try:
            self.client = genai.GenerativeModel(normalized_model)
        except Exception as e:
            # If model not found, try stable gemini-2.5-flash as fallback
            if normalized_model != 'gemini-2.5-flash':
                print(f"Warning: Model {normalized_model} not available, falling back to gemini-2.5-flash (stable): {e}")
                try:
                    self.client = genai.GenerativeModel('gemini-2.5-flash')
                    self.model = 'gemini-2.5-flash'  # Update stored model name
                except Exception as e2:
                    # Last resort: try gemini-1.0-pro (older but stable)
                    print(f"Warning: gemini-2.5-flash also not available, trying gemini-1.0-pro: {e2}")
                    self.client = genai.GenerativeModel('gemini-1.0-pro')
                    self.model = 'gemini-1.0-pro'  # Update stored model name
            else:
                raise
    
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
        
        # Extract usage metadata with defaults for None values
        usage_metadata = {}
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage_metadata = {
                "prompt_tokens": response.usage_metadata.prompt_token_count if hasattr(response.usage_metadata, 'prompt_token_count') and response.usage_metadata.prompt_token_count is not None else 0,
                "completion_tokens": response.usage_metadata.candidates_token_count if hasattr(response.usage_metadata, 'candidates_token_count') and response.usage_metadata.candidates_token_count is not None else 0,
                "total_tokens": response.usage_metadata.total_token_count if hasattr(response.usage_metadata, 'total_token_count') and response.usage_metadata.total_token_count is not None else 0,
            }
        else:
            # Default to 0 if no usage metadata available
            usage_metadata = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
        
        return LLMResponse(
            text=response.text,
            model=self.model,
            usage=usage_metadata,
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

