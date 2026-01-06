"""OpenAI embedding provider implementation."""

from typing import List, Optional, Dict, Any
import openai
from .base import BaseEmbeddingProvider, EmbeddingResponse


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI embedding provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-small", **kwargs):
        """
        Initialize OpenAI embedding provider.
        
        Args:
            api_key: OpenAI API key
            model: Embedding model name (text-embedding-3-small, text-embedding-3-large, etc.)
            **kwargs: Additional configuration
        """
        super().__init__(api_key, model, **kwargs)
        
        if not api_key:
            raise ValueError("OpenAI API key is required")
        
        self.client = openai.AsyncOpenAI(api_key=api_key)
    
    async def generate(
        self,
        texts: List[str],
        **kwargs
    ) -> EmbeddingResponse:
        """Generate embeddings for a list of texts."""
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
            **kwargs
        )
        
        embeddings = [item.embedding for item in response.data]
        
        return EmbeddingResponse(
            embeddings=embeddings,
            model=self.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            metadata={}
        )
    
    async def generate_single(
        self,
        text: str,
        **kwargs
    ) -> List[float]:
        """Generate embedding for a single text."""
        response = await self.client.embeddings.create(
            model=self.model,
            input=[text],
            **kwargs
        )
        
        return response.data[0].embedding

