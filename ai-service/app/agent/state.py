"""État du graphe et événements de traçabilité."""
from __future__ import annotations

import operator
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from ..llm.types import Message, ToolCall

SEVERITY = {"ALLOW": 0, "SANITIZE": 1, "CONFIRM": 2, "BLOCK": 3}


def worst(decisions: list[str]) -> str:
    return max(decisions, key=lambda d: SEVERITY[d]) if decisions else "ALLOW"


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
    confirmation: str | None = None  # approved | denied (décision CONFIRM uniquement)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"stage": self.stage, "module": self.module, "decision": self.decision, "score": self.score, "reason": self.reason, "latencyMs": round(self.latency_ms, 4)}
        if self.verdict is not None:
            d["verdict"] = self.verdict
        if self.confirmation is not None:
            d["confirmation"] = self.confirmation
        return d


class AgentState(TypedDict):
    messages: Annotated[list[Message], operator.add]
    events: Annotated[list[Event], operator.add]
    executed: Annotated[list[dict[str, Any]], operator.add]
    steps: int
    confirmations: int
    pending: tuple[ToolCall, ...]
    final_text: str | None
    halted: str | None  # input_blocked | max_steps | llm_error
    error: str | None
