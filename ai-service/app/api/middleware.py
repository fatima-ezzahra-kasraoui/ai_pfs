"""Contrôles de sécurité transverses : identifiants de requête et de corrélation, taille maximale, en-têtes de sécurité,
journal d'accès, erreurs uniformes (AS-S1-008)."""
from __future__ import annotations

import logging
import re
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .errors import error_body

log = logging.getLogger("agentshield.api")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def install(app: FastAPI, *, stub: bool = False) -> None:
    @app.middleware("http")
    async def secure(request: Request, call_next):  # noqa: ANN001, ANN202
        started = time.perf_counter()
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex  # jamais d'identifiant arbitraire dans les journaux
        correlation = request.headers.get("x-correlation-id", "")
        correlation_id = correlation if _CORRELATION_ID.match(correlation) else None
        request.state.request_id, request.state.correlation_id = request_id, correlation_id
        limit = request.app.state.settings.max_body_bytes
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > limit:
            response: JSONResponse = JSONResponse(error_body(413, "Corps de requête trop volumineux", request_id), status_code=413)
        else:
            try:
                response = await call_next(request)
            except Exception as exc:  # noqa: BLE001 - dernier rempart : réponse générique, détail uniquement dans le journal
                log.error("unhandled path=%s request_id=%s correlation_id=%s error=%s", request.url.path, request_id, correlation_id, type(exc).__name__, exc_info=True)
                response = JSONResponse(error_body(500, "Erreur interne", request_id, detail="erreur interne"), status_code=500)
        response.headers["X-Request-ID"] = request_id
        if correlation_id:
            response.headers["X-Correlation-ID"] = correlation_id
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        if stub:
            response.headers["X-Stub"] = "true"
        # Journal d'accès : jamais de requête (query), de corps ni d'en-tête d'authentification.
        log.info("request method=%s path=%s status=%d ms=%.1f request_id=%s correlation_id=%s", request.method, request.url.path, response.status_code, (time.perf_counter() - started) * 1000, request_id, correlation_id)
        return response
