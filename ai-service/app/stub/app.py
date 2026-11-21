"""Application stub autonome : ``uvicorn app.stub.app:app``. Équivalent à ``AI_STUB=true uvicorn app.main:app``.

Mêmes routes, schémas, authentification et codes que le service réel (``create_app(stub=True)``), faux guards déterministes
(``app.stub.guards``), LLM simulé, en-tête ``X-Stub: true``, ``stub: true`` dans ``/health``. Refusé en recette/production.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI

from ..core.config import Settings
from ..main import create_app


def create_stub_app(settings: Settings | None = None, results_dir: Path | None = None) -> FastAPI:
    base = settings or Settings.from_env()
    forced = replace(base, stub=True, llm=replace(base.llm, provider="mock"))  # le stub n'appelle jamais un LLM réel
    kwargs = {} if results_dir is None else {"results_dir": results_dir}
    return create_app(forced, **kwargs)


app = create_stub_app()
