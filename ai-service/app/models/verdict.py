"""Modèle commun ``Verdict`` (Annexes C et D du dossier, AS-S1-002).

Un guard ne prend jamais de décision : il renvoie un ``Verdict`` avec un score et
une raison. La décision (ALLOW / SANITIZE / CONFIRM / BLOCK) appartient au moteur
de décision. Le champ ``decision`` reste donc ``None`` côté guard.

Ce fichier est le contrat partagé : toute modification passe par une PR relue
par É2 et É3 et incrémente le tag ``contract-vX.Y``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Decision(str, Enum):
    ALLOW = "ALLOW"
    SANITIZE = "SANITIZE"
    CONFIRM = "CONFIRM"
    BLOCK = "BLOCK"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AttackType(str, Enum):
    DIRECT_INJECTION = "direct_injection"
    INDIRECT_INJECTION = "indirect_injection"
    DATA_LEAK = "data_leak"
    TOOL_ABUSE = "tool_abuse"
    NONE = "none"


MODULES = ("A", "B", "C", "D", "ENGINE")


def risk_from_score(score: float) -> RiskLevel:
    """Niveau de risque indicatif dérivé du seul score du détecteur.

    Le niveau final tient aussi compte de l'outil visé (calculé par le moteur) ;
    score et niveau de risque restent deux champs distincts.
    """
    if score >= 0.9:
        return RiskLevel.HIGH
    if score >= 0.5:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


@dataclass
class Verdict:
    module: str
    score: float
    attack_type: str
    reason: str
    cleaned: str | None = None
    risk_level: str = RiskLevel.LOW.value
    decision: str | None = None
    correlation_id: str | None = None
    degraded: bool = False
    latency_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.module not in MODULES:
            raise ValueError(f"module inconnu : {self.module!r}")
        if not isinstance(self.score, (int, float)) or isinstance(self.score, bool):
            raise ValueError("score doit être un nombre")
        if not 0.0 <= float(self.score) <= 1.0:
            raise ValueError(f"score hors de [0 ; 1] : {self.score}")
        self.score = float(self.score)
        self.attack_type = AttackType(self.attack_type).value
        self.risk_level = RiskLevel(self.risk_level).value
        if self.decision is not None:
            self.decision = Decision(self.decision).value

    def to_dict(self) -> dict[str, Any]:
        """Représentation JSON conforme à ``docs/contract/verdict.schema.json``."""
        data: dict[str, Any] = {
            "module": self.module,
            "attackType": self.attack_type,
            "score": round(self.score, 6),
            "riskLevel": self.risk_level,
            "decision": self.decision,
            "reason": self.reason,
            "correlationId": self.correlation_id,
            "cleaned": self.cleaned,
            "degraded": self.degraded,
        }
        if self.latency_ms is not None:
            data["latencyMs"] = round(self.latency_ms, 3)
        if self.metadata:
            data["metadata"] = self.metadata
        return data


class Guard:
    """Interface commune des guards : ``check(contexte) -> Verdict``."""

    module: str = ""

    def check(self, context: dict[str, Any]) -> Verdict:  # pragma: no cover
        raise NotImplementedError
