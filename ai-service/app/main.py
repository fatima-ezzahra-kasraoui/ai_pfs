"""Service IA AgentShield (FastAPI)."""
from __future__ import annotations

import logging

from fastapi import FastAPI

from evaluation.results import RESULTS_DIR

from .agent.service import AgentService
from .api import agent, errors, health, metrics, middleware, security
from .core.config import POLICY_PATH, Settings
from .core.policy import PolicyStore
from .guards.coherence import default_checker
from .llm import LLMConfigError, build_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("agentshield.app")
VERSION = health.VERSION


def create_app(settings: Settings | None = None, guards: dict | None = None, results_dir=RESULTS_DIR, llm=None, stub: bool | None = None, policy=None) -> FastAPI:
    """``llm`` : client LLM injecté (tests) ; sinon construit depuis ``settings.llm`` (variables ``LLM_*``).

    ``policy`` : ``PolicyStore`` ou ``Policy`` injecté (tests) ; sinon ``config/policy.yaml`` (``POLICY_PATH``). Une politique invalide empêche le
    démarrage (échec fermé, ``PolicyError``) ; rechargée à chaud ensuite (l'ancienne politique valide reste active si le nouveau fichier est invalide).

    ``stub`` (défaut : ``settings.stub``, variable ``AI_STUB``) : faux service IA contractuel, refusé en recette et en production.
    """
    settings = settings or Settings.from_env()
    stub = settings.stub if stub is None else stub
    if stub:
        settings.validate()
        from .llm.providers.mock import SimulatedLLM
        from .stub.guards import stub_guards

        guards, llm, results_dir = stub_guards(), SimulatedLLM(), _empty_results_dir() if results_dir is RESULTS_DIR else results_dir
        log.warning("STUB ACTIF : les verdicts sont des fixtures, aucune détection réelle (AI_STUB=true)")
    app = FastAPI(
        title="AgentShield AI service", version=VERSION,
        docs_url="/docs" if settings.expose_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.expose_docs else None,
    )
    app.state.settings = settings
    app.state.guards = guards if guards is not None else security.build_guards()
    app.state.results_dir = results_dir
    app.state.stub = stub
    app.state.policy = policy if policy is not None else PolicyStore(POLICY_PATH)
    app.state.llm_error = None
    app.state.agent = None
    try:
        client = llm if llm is not None else build_client(settings.llm)
        judge = client if settings.coherence_llm_judge and not client.simulated else None
        coherence = default_checker(settings.coherence_embedding_model, judge, provider=settings.coherence_embedding_provider, base_url=settings.coherence_embedding_url, timeout_s=settings.coherence_embedding_timeout_s)
        app.state.agent = AgentService(client, app.state.guards, max_steps=settings.agent_max_steps, policy=app.state.policy, coherence=coherence)
        app.state.llm_info = {"provider": client.name, "simulated": client.simulated}
    except LLMConfigError as exc:
        # Échec fermé limité à l'agent : les guards restent disponibles. Le message ne contient jamais de secret.
        app.state.llm_error = str(exc)
        app.state.llm_info = {"provider": settings.llm.provider, "simulated": settings.llm.provider == "mock"}
        log.error("agent désactivé : %s", exc)
    middleware.install(app, stub=stub)
    errors.install(app)
    app.include_router(security.router)
    app.include_router(metrics.router)
    app.include_router(agent.router)
    app.include_router(health.protected)
    app.include_router(health.public)
    return app


def _empty_results_dir():
    import tempfile
    from pathlib import Path

    return Path(tempfile.mkdtemp(prefix="agentshield-stub-"))  # le stub n'affiche aucun chiffre factice : « Évaluation à venir »


app = create_app()
