"""Embedding provider abstraction layer."""

from .base import BaseEmbeddingProvider, EmbeddingResponse
from .gemini import GeminiEmbeddingProvider
try:
    from .openai import OpenAIEmbeddingProvider
except ImportError:
    OpenAIEmbeddingProvider = None

__all__ = [
    "BaseEmbeddingProvider",
    "EmbeddingResponse",
    "GeminiEmbeddingProvider",
    "OpenAIEmbeddingProvider",
]

