"""POST /internal/agent/run (AS-S1-023).

Authentification : en-tête ``X-AI-Service-Key`` (même mécanisme que ``/internal/security/analyze``, échec fermé).
Traçabilité : ``correlationId`` repris dans la réponse et les journaux, ``runId`` généré, ``X-Request-ID`` posé par le middleware.
Le message, les contenus d'outils et la réponse ne sont jamais écrits dans les journaux.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from ..agent.service import AgentService, ConfigurationError, PolicyUnavailableError, RunInput
from ..core.config import PRODUCTION_LIKE_ENVS
from .agent_schemas import AgentRunRequest, AgentRunResponse
from .security import require_service_key

router = APIRouter(prefix="/internal/agent", dependencies=[Depends(require_service_key)])
log = logging.getLogger("agentshield.api")

def _agent(request: Request) -> AgentService:
    agent: AgentService | None = getattr(request.app.state, "agent", None)
    if agent is None:
        raise HTTPException(status_code=503, detail="agent indisponible : configuration du LLM invalide")
    return agent


@router.post("/run", response_model=AgentRunResponse, response_model_by_alias=True)
def run_agent(body: AgentRunRequest, request: Request) -> dict:
    agent = _agent(request)
    if body.confirmation_policy in {"approve", "auto"} and request.app.state.settings.env in PRODUCTION_LIKE_ENVS:
        raise HTTPException(status_code=422, detail="confirmationPolicy approve/auto simule une approbation : interdit en recette et en production")
    run_input = RunInput(
        message=body.message, scenario_id=body.scenario_id,
        tool_fixture=body.tool_fixture.model_dump() if body.tool_fixture else None,
        mode=body.mode, config=body.config, seed=body.seed, correlation_id=body.correlation_id or getattr(request.state, "correlation_id", None),
        confirmation_policy=body.confirmation_policy,
        attack_goal=body.attack_goal.model_dump(exclude_none=True) if body.attack_goal else None,
        legit_goal=body.legit_goal.model_dump(exclude_none=True) if body.legit_goal else None,
    )
    try:
        return agent.run(run_input).to_dict()
    except ConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PolicyUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
