"""POST /internal/security/analyze : exécute un guard et renvoie son Verdict (AS-S2-014)."""
from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from ..core.config import Settings
from .schemas import AnalyzeRequest, VerdictModel

router = APIRouter(prefix="/internal")
log = logging.getLogger("agentshield.api")


def require_service_key(request: Request, x_ai_service_key: str | None = Header(default=None)) -> None:
    expected: str = request.app.state.settings.service_key
    # Échec fermé : clé non configurée => refus. Comparaison à temps constant.
    if not expected or not x_ai_service_key or not hmac.compare_digest(expected, x_ai_service_key):
        raise HTTPException(status_code=401, detail="clé de service absente ou invalide")


@router.post("/security/analyze", response_model=VerdictModel, response_model_by_alias=True, dependencies=[Depends(require_service_key)])
def analyze(body: AnalyzeRequest, request: Request) -> dict:
    guards = request.app.state.guards
    guard = guards[body.module]
    if body.module == "D":
        if body.text is None and body.arguments is None:
            raise HTTPException(status_code=422, detail="'text' ou 'arguments' requis pour le Guard D")
        ctx = {"text": body.text, "arguments": body.arguments, "channel": "tool_arguments" if body.arguments is not None else body.channel}
    else:
        if body.text is None:
            raise HTTPException(status_code=422, detail="'text' requis")
        ctx = {"text": body.text}
    ctx["correlation_id"] = body.correlation_id
    verdict = guard.check(ctx)
    # Jamais le contenu analysé dans les journaux : seulement le module, le score et l'identifiant.
    log.info("analyze module=%s score=%.3f correlation_id=%s degraded=%s", body.module, verdict.score, body.correlation_id, verdict.degraded)
    return verdict.to_dict()


def build_guards(settings: Settings | None = None) -> dict:
    from ..core.config import POLICY_PATH
    from ..guards.classifier import load_classifier
    from ..guards.content_guard import ContentGuard
    from ..guards.input_guard import InputGuard
    from ..guards.output_guard import OutputGuard, try_load_presidio

    classifier = load_classifier()
    detector = try_load_presidio()
    output = OutputGuard.from_policy(POLICY_PATH, detector) if POLICY_PATH.exists() else OutputGuard(person_detector=detector)
    return {"A": InputGuard(classifier), "B": ContentGuard(classifier), "D": output}
