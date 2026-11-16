"""Configuration du service (variables d'environnement, jamais de secret en dur)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

POLICY_PATH = Path(os.environ.get("POLICY_PATH", Path(__file__).resolve().parents[2] / "config" / "policy.yaml"))


@dataclass(frozen=True)
class Settings:
    service_key: str

    @classmethod
    def from_env(cls) -> Settings:
        # Pas de valeur par défaut : sans clé configurée, tout appel est refusé (échec fermé).
        return cls(service_key=os.environ.get("AI_SERVICE_KEY", ""))
