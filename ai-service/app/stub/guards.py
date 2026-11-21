"""Faux guards DÉTERMINISTES pour le stub (AS-S1-010).

Ils ne détectent RIEN : le score vaut 0 par défaut ; il n'est élevé que si l'appelant l'a demandé explicitement
dans le texte avec le marqueur ``[[stub:score=0.95]]``. Chaque verdict est signalé ``degraded=True``,
``metadata.stub=true`` et sa raison commence par « [STUB] » : un résultat de stub ne peut pas être pris pour une détection réelle.
"""
from __future__ import annotations

import re
from typing import Any

from ..models.verdict import AttackType, Guard, Verdict, risk_from_score

MARKER = re.compile(r"\[\[stub:score=(0(?:\.\d+)?|1(?:\.0+)?)\]\]")
ATTACK_BY_MODULE = {"A": AttackType.DIRECT_INJECTION, "B": AttackType.INDIRECT_INJECTION, "D": AttackType.DATA_LEAK}


class StubGuard(Guard):
    degraded = True

    def __init__(self, module: str) -> None:
        if module not in ATTACK_BY_MODULE:
            raise ValueError(f"module de stub inconnu : {module!r}")
        self.module = module

    def check(self, context: dict[str, Any]) -> Verdict:
        text = context.get("text")
        if text is None and context.get("arguments") is not None:
            text = str(context["arguments"])
        text = str(text or "")
        m = MARKER.search(text)
        score = float(m.group(1)) if m else 0.0
        flagged = score > 0
        visible = MARKER.sub("", text)
        meta: dict[str, Any] = {"stub": True, "trigger": "marker" if flagged else None}
        if self.module == "D":
            meta |= {"canary": False, "channel": str(context.get("channel") or "final_response"), "kinds": ["stub"] if flagged else [], "findings": []}
        return Verdict(
            module=self.module, score=score,
            attack_type=(ATTACK_BY_MODULE[self.module] if flagged else AttackType.NONE).value,
            reason=f"[STUB] {'score imposé par le marqueur de test' if flagged else 'aucune détection (le stub ne détecte rien)'}",
            cleaned="[STUB-MASQUÉ]" if flagged and self.module == "D" else visible,
            risk_level=risk_from_score(score).value,
            correlation_id=context.get("correlation_id") or context.get("correlationId"),
            degraded=True, latency_ms=0.0, metadata=meta,
        )


def stub_guards() -> dict[str, StubGuard]:
    return {m: StubGuard(m) for m in ATTACK_BY_MODULE}
