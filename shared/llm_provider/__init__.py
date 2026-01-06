"""LLM provider abstraction layer."""

from .base import BaseLLMProvider, LLMResponse, LLMStreamChunk
from .gemini import GeminiProvider

# Optional providers (only import if available)
try:
    from .openai import OpenAIProvider
except ImportError:
    OpenAIProvider = None

try:
    from .anthropic import AnthropicProvider
except ImportError:
    AnthropicProvider = None

__all__ = [
    "BaseLLMProvider",
    "LLMResponse",
    "LLMStreamChunk",
    "GeminiProvider",
]
if OpenAIProvider:
    __all__.append("OpenAIProvider")
if AnthropicProvider:
    __all__.append("AnthropicProvider")

