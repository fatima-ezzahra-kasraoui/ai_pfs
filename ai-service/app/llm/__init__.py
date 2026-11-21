"""Couche d'intégration LLM (AS-S1-009) : configuration, client, fournisseurs, simulation."""
from .client import LLMClient, build_client
from .config import LLMConfig
from .errors import LLMConfigError, LLMError, LLMProviderError, LLMResponseError, LLMTimeoutError
from .types import LLMResponse, Message, ToolCall, ToolSpec

__all__ = [
    "LLMClient", "LLMConfig", "LLMConfigError", "LLMError", "LLMProviderError", "LLMResponse",
    "LLMResponseError", "LLMTimeoutError", "Message", "ToolCall", "ToolSpec", "build_client",
]
