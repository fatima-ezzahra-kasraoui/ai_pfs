"""État du graphe et événements de traçabilité."""
from __future__ import annotations

import operator
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from ..core.engine import SEVERITY, worst  # noqa: F401  (source unique de l'ordre de sévérité)
from ..llm.types import Message, ToolCall


@dataclass
class Event:
    """Une étape de contrôle (format repris de ``evaluation.runners.HTTPRunner``) ; ``verdict`` : Verdict du guard (sans ``cleaned``)."""

    stage: str  # input | tool_call | tool_content | final_response
    module: str  # A | B | C | D
    decision: str
    score: float | None = None
    reason: str = ""
    latency_ms: float = 0.0
    verdict: dict[str, Any] | None = None
    confirmation: str | None = None  # approved | denied | pending (décision CONFIRM uniquement)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"stage": self.stage, "module": self.module, "decision": self.decision, "score": self.score, "reason": self.reason, "latencyMs": round(self.latency_ms, 4)}
        if self.verdict is not None:
            d["verdict"] = self.verdict
        if self.confirmation is not None:
            d["confirmation"] = self.confirmation
        return d


class AgentState(TypedDict):
    user_text: str  # message utilisateur transmis au LLM (éventuellement nettoyé par la protection)
    messages: Annotated[list[Message], operator.add]  # suite de la conversation : appels et résultats d'outils
    events: Annotated[list[Event], operator.add]
    executed: Annotated[list[dict[str, Any]], operator.add]
    steps: int
    confirmations: int
    pending: tuple[ToolCall, ...]
    final_text: str | None
    halted: str | None  # input_blocked | awaiting_confirmation | max_steps | llm_error
    attempts: Annotated[list[dict[str, Any]], operator.add]  # tous les appels d'outils demandés par le LLM (exécutés ou non)
    pending_action: dict[str, Any] | None  # action suspendue en attente de confirmation (AS-S2-017)
    error: str | None
