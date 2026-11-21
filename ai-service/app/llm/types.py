"""Types neutres échangés entre l'agent et les fournisseurs LLM (indépendants de tout SDK)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class ToolSpec:
    """Description d'un outil exposé au modèle (``parameters`` : JSON Schema d'un objet)."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()  # rôle assistant : appels d'outils demandés
    tool_call_id: str | None = None  # rôle tool : appel auquel ce résultat répond
    name: str | None = None  # rôle tool : nom de l'outil


@dataclass(frozen=True)
class LLMResponse:
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    stop_reason: str = "end"
    usage: dict[str, int] = field(default_factory=dict)
