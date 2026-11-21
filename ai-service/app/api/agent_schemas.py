"""Schémas de ``POST /internal/agent/run`` (AS-S1-023, contrat docs/contract/openapi-internal.yaml).

Compatibles avec le contrat provisoire d'``evaluation.runners.HTTPRunner`` (scenarioId, message, toolFixture, mode,
config, seed -> attackSucceeded, taskSucceeded, finalDecision, confirmations, totalMs, events).
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..agent.tools import TOOL_NAMES
from .schemas import VerdictModel

MAX_MESSAGE_CHARS = 8_000
MAX_FIXTURE_CHARS = 200_000
ToolName = Literal["read_email", "browse_web", "read_file", "send_email", "delete_file"]
DecisionName = Literal["ALLOW", "SANITIZE", "CONFIRM", "BLOCK"]
assert set(TOOL_NAMES) == set(ToolName.__args__)  # type: ignore[attr-defined]  # une seule liste d'outils dans tout le code


class ToolFixture(BaseModel):
    """Contenu imposé à l'outil nommé (simule une réponse d'outil, éventuellement piégée)."""

    model_config = ConfigDict(extra="forbid")

    name: ToolName
    content: str = Field(max_length=MAX_FIXTURE_CHARS)


class Goal(BaseModel):
    """Objectif de l'attaquant (``attackGoal``) ou de la tâche légitime (``legitGoal``), pour calculer l'issue."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["tool_call", "leak"]
    tool: ToolName | None = None
    secret: str | None = Field(default=None, max_length=256)
    to: str | None = Field(default=None, max_length=254)
    path: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _coherent(self) -> Goal:
        if self.kind == "tool_call" and self.tool is None:
            raise ValueError("'tool' requis pour kind=tool_call")
        if self.kind == "leak" and not self.secret:
            raise ValueError("'secret' requis pour kind=leak")
        return self


class AgentRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    scenario_id: str | None = Field(default=None, alias="scenarioId", max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    tool_fixture: ToolFixture | None = Field(default=None, alias="toolFixture")
    mode: Literal["protected", "unprotected"] | None = None
    config: str | None = Field(default=None, max_length=32)
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)
    correlation_id: str | None = Field(default=None, alias="correlationId", max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    confirmation_policy: Literal["deny", "approve", "auto"] = Field(default="deny", alias="confirmationPolicy")
    attack_goal: Goal | None = Field(default=None, alias="attackGoal")
    legit_goal: Goal | None = Field(default=None, alias="legitGoal")

    @field_validator("message")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("le message ne peut pas être vide")
        return v

    @model_validator(mode="after")
    def _one_goal(self) -> AgentRunRequest:
        if self.attack_goal and self.legit_goal:
            raise ValueError("attackGoal et legitGoal sont exclusifs")
        return self


class AgentEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    stage: Literal["input", "tool_call", "tool_content", "final_response"]
    module: Literal["A", "B", "C", "D", "ENGINE"]
    decision: DecisionName
    score: float | None = None
    reason: str = ""
    latency_ms: float = Field(default=0.0, alias="latencyMs")
    verdict: VerdictModel | None = None
    confirmation: Literal["approved", "denied"] | None = None


class ToolCallRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tool: ToolName
    args: dict[str, Any]
    output: dict[str, Any]
    simulated: bool = True
    side_effect: str | None = Field(default=None, alias="sideEffect")


class SimulatedState(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    outbox: list[dict[str, str]]
    deleted_files: list[str] = Field(alias="deletedFiles")


class LLMInfo(BaseModel):
    provider: str
    simulated: bool


class AgentInfo(BaseModel):
    name: str
    simulated_tools: bool = Field(alias="simulatedTools")
    model_config = ConfigDict(populate_by_name=True)


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="runId")
    correlation_id: str | None = Field(default=None, alias="correlationId")
    scenario_id: str | None = Field(default=None, alias="scenarioId")
    mode: Literal["protected", "unprotected"]
    config: str
    seed: int | None = None
    response: str
    final_decision: DecisionName = Field(alias="finalDecision")
    halted: Literal["input_blocked", "max_steps", "llm_error"] | None = None
    error: str | None = None
    confirmations: int = Field(ge=0)
    attack_succeeded: bool | None = Field(default=None, alias="attackSucceeded", description="null : aucun objectif d'attaque connu.")
    task_succeeded: bool | None = Field(default=None, alias="taskSucceeded", description="null : exécution d'attaque ou objectif inconnu.")
    total_ms: float = Field(alias="totalMs")
    steps: int
    events: list[AgentEvent]
    tool_calls: list[ToolCallRecord] = Field(alias="toolCalls")
    simulated_state: SimulatedState = Field(alias="simulatedState")
    llm: LLMInfo
    agent: AgentInfo
