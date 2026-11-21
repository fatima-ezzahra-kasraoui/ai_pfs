"""Format d'erreur commun, sans détail interne (AS-S1-008).

Surensemble compatible : ``status``, ``code`` et ``message`` reprennent le format du backend Spring (``ApiError``) ;
``detail`` conserve le champ historique de FastAPI ; ``requestId`` relie l'erreur au journal. Les erreurs de validation
ne renvoient JAMAIS la valeur reçue (``input``/``ctx`` de Pydantic sont retirés : elle pourrait contenir un secret).
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

CODES = {400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 413: "PAYLOAD_TOO_LARGE", 422: "VALIDATION_ERROR", 500: "INTERNAL_ERROR", 501: "NOT_IMPLEMENTED", 503: "SERVICE_UNAVAILABLE"}


def error_body(status: int, message: str, request_id: str | None, detail: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"status": status, "code": CODES.get(status, "HTTP_ERROR"), "message": message, "detail": message if detail is None else detail}
    if request_id:
        body["requestId"] = request_id
    return body


def install(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Requête refusée"
        return JSONResponse(error_body(exc.status_code, message, getattr(request.state, "request_id", None)), status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        problems = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")} for e in exc.errors()]
        return JSONResponse(error_body(422, "Requête invalide", getattr(request.state, "request_id", None), detail=problems), status_code=422)
