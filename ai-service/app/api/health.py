"""``GET /internal/health`` (clé de service requise, AS-S1-008) et ``GET /health`` (public, healthcheck Docker)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Request

from .security import require_service_key

VERSION = "1.1.0"
protected = APIRouter(prefix="/internal", dependencies=[Depends(require_service_key)])
public = APIRouter()


def health_body(app: FastAPI) -> dict:
    degraded = {m: bool(g.degraded) for m, g in app.state.guards.items()}
    body: dict = {"status": "ok", "degraded": degraded, "version": VERSION, "agent": {"available": app.state.agent is not None, **app.state.llm_info}}
    if app.state.llm_error:
        body["agent"]["error"] = "configuration du LLM invalide"
    if app.state.stub:
        body["stub"] = True
    return body


@protected.get("/health")
def internal_health(request: Request) -> dict:
    """État du service pour le backend (appel authentifié : sans clé, 401)."""
    return health_body(request.app)


@public.get("/health")
def container_health(request: Request) -> dict:
    """Healthcheck du conteneur (Docker Compose, sans clé : n'expose aucun secret)."""
    return health_body(request.app)
