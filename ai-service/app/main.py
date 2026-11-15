"""Service IA AgentShield (FastAPI)."""
from __future__ import annotations

import logging

from fastapi import FastAPI

from evaluation.results import RESULTS_DIR

from .api import metrics, security
from .core.config import Settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(settings: Settings | None = None, guards: dict | None = None, results_dir=RESULTS_DIR) -> FastAPI:
    app = FastAPI(title="AgentShield AI service", version="1.0.0", docs_url="/docs")
    app.state.settings = settings or Settings.from_env()
    app.state.guards = guards if guards is not None else security.build_guards()
    app.state.results_dir = results_dir
    app.include_router(security.router)
    app.include_router(metrics.router)

    @app.get("/health")
    def health() -> dict:
        degraded = {m: bool(g.degraded) for m, g in app.state.guards.items()}
        return {"status": "ok", "degraded": degraded}

    return app


app = create_app()
