"""Schémas de requête/réponse de l'API interne (contrat OpenAPI, AS-S2-014)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_TEXT_CHARS = 200_000


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    module: Literal["A", "B", "D"] = Field(description="Guard à exécuter (C et moteur : service de l'agent).")
    text: str | None = Field(default=None, max_length=MAX_TEXT_CHARS)
    arguments: dict[str, Any] | None = Field(default=None, description="Arguments d'outil (Guard D, canal tool_arguments).")
    channel: Literal["user_input", "tool_content", "final_response", "tool_arguments"] = "user_input"
    correlation_id: str | None = Field(default=None, alias="correlationId", max_length=128)


class VerdictModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    module: str
    attack_type: str = Field(alias="attackType")
    score: float = Field(ge=0, le=1)
    risk_level: str = Field(alias="riskLevel")
    decision: str | None = None
    reason: str
    correlation_id: str | None = Field(default=None, alias="correlationId")
    cleaned: str | None = None
    degraded: bool = False
    latency_ms: float | None = Field(default=None, alias="latencyMs")
    metadata: dict[str, Any] | None = None
