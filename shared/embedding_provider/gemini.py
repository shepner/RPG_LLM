"""Google Gemini embedding provider implementation."""

import os
from typing import List, Optional, Dict, Any
import google.generativeai as genai
from .base import BaseEmbeddingProvider, EmbeddingResponse


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """Google Gemini embedding provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "models/embedding-001", **kwargs):
        """
        Initialize Gemini embedding provider.
        
        Args:
            api_key: Gemini API key (or use GOOGLE_APPLICATION_CREDENTIALS)
            model: Embedding model name
            **kwargs: Additional configuration
        """
        super().__init__(api_key, model, **kwargs)
        
        # Configure Gemini
        if api_key:
            genai.configure(api_key=api_key)
        elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            genai.configure()
        else:
            raise ValueError("Either api_key or GOOGLE_APPLICATION_CREDENTIALS must be provided")
    
    async def generate(
        self,
        texts: List[str],
        **kwargs
    ) -> EmbeddingResponse:
        """Generate embeddings for a list of texts."""
        import asyncio
        
        # Process texts in batch
        loop = asyncio.get_event_loop()
        
        async def embed_text(text: str):
            result = await loop.run_in_executor(
                None,
                lambda: genai.embed_content(
                    model=self.model,
                    content=text,
                    task_type="retrieval_document"  # or "retrieval_query", "semantic_similarity", etc.
                )
            )
            return result['embedding']
        
        # Process all texts concurrently
        embeddings = await asyncio.gather(*[embed_text(text) for text in texts])
        
        return EmbeddingResponse(
            embeddings=embeddings,
            model=self.model,
            usage={"texts": len(texts)},
            metadata={}
        )
    
    async def generate_single(
        self,
        text: str,
        **kwargs
    ) -> List[float]:
        """Generate embedding for a single text."""
        import asyncio
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: genai.embed_content(
                model=self.model,
                content=text,
                task_type=kwargs.get("task_type", "retrieval_document")
            )
        )
        
        return result['embedding']

