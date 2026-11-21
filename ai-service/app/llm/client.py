"""Interface ``LLMClient`` et fabrique : le reste de l'application ne dépend que de ce module."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import httpx

from .config import LLMConfig
from .types import LLMResponse, Message, ToolSpec


class LLMClient(Protocol):
    name: str
    simulated: bool  # True : aucune inférence réelle (résultats à ne jamais présenter comme ceux d'un vrai modèle)

    def complete(self, system: str, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()) -> LLMResponse: ...


def build_client(config: LLMConfig, transport: httpx.BaseTransport | None = None) -> LLMClient:
    """Construit le client du fournisseur configuré. ``transport`` sert aux tests (aucun réseau)."""
    config.validate()
    if config.provider == "mock":
        from .providers.mock import SimulatedLLM

        return SimulatedLLM()
    if config.provider == "anthropic":
        from .providers.anthropic import AnthropicClient

        return AnthropicClient(config, transport)
    from .providers.openai_compat import OpenAICompatibleClient

    return OpenAICompatibleClient(config, transport)
