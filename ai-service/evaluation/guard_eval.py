"""Évaluation d'un guard sur un jeu de cas étiquetés (briques partagées).

Un guard renvoie un *score* ; la mesure binaire « détecté / non détecté » applique le seuil
``injection_review`` de policy.yaml (toute intervention : SANITIZE, CONFIRM ou BLOCK). Le
choix du seuil appartient au moteur de décision, pas au guard.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from app.guards.content_guard import ContentGuard
from app.guards.input_guard import InputGuard
from app.guards.output_guard import OutputGuard

from .dataio import Example
from .metrics import classification_report, latency_summary

POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "policy.yaml"


def load_thresholds(path: Path = POLICY_PATH) -> dict[str, float]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    th = data.get("thresholds") or {}
    return {k: float(v) for k, v in th.items()}


def score_input_guard(guard: InputGuard, examples: Sequence[Example]) -> list[dict[str, Any]]:
    out = []
    for ex in examples:
        v = guard.check({"text": ex.text})
        out.append({"id": ex.id, "label": ex.label, "score": round(v.score, 6), "latencyMs": round(v.latency_ms or 0.0, 4), "rules": v.metadata.get("rules", [])})
    return out


def score_content_guard(guard: ContentGuard, cases: Sequence[dict]) -> list[dict[str, Any]]:
    out = []
    for c in cases:
        v = guard.check({"text": c["text"]})
        out.append({"id": c["id"], "label": c["label"], "score": round(v.score, 6), "latencyMs": round(v.latency_ms or 0.0, 4), "wrapper": c.get("wrapper")})
    return out


def score_output_guard(guard: OutputGuard, cases: Sequence[dict]) -> list[dict[str, Any]]:
    out = []
    for c in cases:
        v = guard.check({"text": c["text"]})
        leaked = c["secret"] is not None and c["secret"] in (v.cleaned or "")
        out.append({"id": c["id"], "label": c["label"], "score": round(v.score, 6), "latencyMs": round(v.latency_ms or 0.0, 4), "kind": c.get("kind"), "secretStillInClear": leaked})
    return out


def summarize(scored: Sequence[dict[str, Any]], threshold: float) -> dict[str, Any]:
    y_true = [r["label"] for r in scored]
    y_pred = [1 if r["score"] >= threshold else 0 for r in scored]
    report = classification_report(y_true, y_pred)
    report["threshold"] = threshold
    report["latencyMs"] = latency_summary([r["latencyMs"] for r in scored])
    return report


def misclassified(scored: Sequence[dict[str, Any]], threshold: float) -> dict[str, list[dict[str, Any]]]:
    fn = [r for r in scored if r["label"] == 1 and r["score"] < threshold]
    fp = [r for r in scored if r["label"] == 0 and r["score"] >= threshold]
    return {"falseNegatives": fn, "falsePositives": fp}
