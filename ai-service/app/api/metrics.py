"""GET /internal/metrics : résultats d'évaluation mesurés (AS-S3-021).

Ne renvoie que le contenu des fichiers produits par ``evaluation/`` : aucun chiffre n'est
calculé ni inventé ici. Sans résultat, la réponse l'indique (« Évaluation à venir »).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from evaluation.results import load_results

from .security import require_service_key

router = APIRouter(prefix="/internal")


def _latest(results: list[dict], kind: str, official_only: bool) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in results:
        if r["kind"] != kind or (official_only and r["status"] != "official"):
            continue
        key = r["name"]
        if key not in out or r["generatedAt"] > out[key]["generatedAt"]:
            out[key] = r
    return out


def _public(r: dict) -> dict:
    keep = {k: r[k] for k in ("name", "kind", "split", "status", "generatedAt", "commit", "dirty", "seed", "config", "metrics") if k in r}
    keep["metrics"] = {k: v for k, v in r["metrics"].items() if k != "errors"}
    keep["notes"] = r.get("notes", [])
    return keep


@router.get("/metrics", dependencies=[Depends(require_service_key)])
def metrics(request: Request, include_preliminary: bool = True) -> dict:
    results = load_results(request.app.state.results_dir)
    if not results:
        return {"status": "not_available", "available": False, "message": "Évaluation à venir : aucun résultat mesuré.", "results": []}
    chosen: list[dict] = []
    for kind in ("detection", "benchmark", "ablation", "threshold_tuning"):
        chosen += list(_latest(results, kind, official_only=not include_preliminary).values())
    return {"status": "ok" if chosen else "not_available", "available": bool(chosen), "message": None if chosen else "Évaluation à venir : aucun résultat officiel.", "results": [_public(r) for r in chosen]}
