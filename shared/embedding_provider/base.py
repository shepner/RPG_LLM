"""Base embedding provider interface."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import numpy as np


class EmbeddingResponse(BaseModel):
    """Embedding response model."""
    
    embeddings: List[List[float]]  # List of embedding vectors
    model: str
    usage: Optional[Dict[str, int]] = None  # tokens, etc.
    metadata: Dict[str, Any] = {}


class BaseEmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "default", **kwargs):
        """
        Initialize embedding provider.
        
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
        texts: List[str],
        **kwargs
    ) -> EmbeddingResponse:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of texts to embed
            **kwargs: Additional provider-specific parameters
            
        Returns:
            EmbeddingResponse object with embeddings
        """
        pass
    
    @abstractmethod
    async def generate_single(
        self,
        text: str,
        **kwargs
    ) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Embedding vector as list of floats
        """
        pass

