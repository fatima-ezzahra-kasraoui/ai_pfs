"""Configuration du service (variables d'environnement, jamais de secret en dur)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ..llm.config import LLMConfig

POLICY_PATH = Path(os.environ.get("POLICY_PATH", Path(__file__).resolve().parents[2] / "config" / "policy.yaml"))


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    return default if not raw else raw in {"1", "true", "yes", "on"}


ENVS = ("dev", "test", "recette", "production")
STUB_FORBIDDEN_ENVS = ("recette", "production")
PRODUCTION_LIKE_ENVS = STUB_FORBIDDEN_ENVS  # profils où aucune simulation (stub, approbation simulée) n'est admise


class StubForbiddenError(RuntimeError):
    """Le stub (AI_STUB=true) ne doit jamais être actif en recette ni en production (AS-S1-010)."""


@dataclass(frozen=True)
class Settings:
    service_key: str
    # --- ajouts AS-S1-008/009 (valeurs par défaut : le constructeur Settings(service_key=...) reste valide) ---
    env: str = "dev"  # dev | test | recette | production
    expose_docs: bool = True  # /docs et /openapi.json ; désactivé par défaut en production
    max_body_bytes: int = 1_048_576  # taille maximale d'un corps de requête (Content-Length)
    agent_max_steps: int = 6  # nombre maximal d'appels LLM par exécution de l'agent
    llm: LLMConfig = field(default_factory=LLMConfig)
    coherence_embedding_model: str = ""  # COHERENCE_EMBEDDING_MODEL : modèle sentence-transformers ; vide = pas d'embeddings (repli lexical)
    coherence_llm_judge: bool = False  # COHERENCE_LLM_JUDGE=true : juge LLM en plan B (ignoré avec le LLM simulé)
    stub: bool = False  # AI_STUB=true : faux service IA contractuel (fixtures), interdit en recette et en production

    coherence_embedding_provider: str = "sentence_transformers"
    coherence_embedding_url: str = "http://localhost:11434"
    coherence_embedding_timeout_s: float = 120.0

    def validate(self) -> None:
        """Échec fermé au démarrage : le stub ne peut pas être actif dans un profil de recette ou de production."""
        if self.stub and self.env in STUB_FORBIDDEN_ENVS:
            raise StubForbiddenError(f"AI_STUB=true est interdit avec AI_ENV={self.env}")

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ.get("AI_ENV", "dev").strip().lower() or "dev"
        return cls(
            # Pas de valeur par défaut : sans clé configurée, tout appel est refusé (échec fermé).
            service_key=os.environ.get("AI_SERVICE_KEY", ""),
            env=env,
            expose_docs=_flag("AI_EXPOSE_DOCS", env not in STUB_FORBIDDEN_ENVS),
            max_body_bytes=int(os.environ.get("AI_MAX_BODY_BYTES", "1048576") or 1_048_576),
            agent_max_steps=int(os.environ.get("AGENT_MAX_STEPS", "6") or 6),
            llm=LLMConfig.from_env(),
            coherence_embedding_model=os.environ.get("COHERENCE_EMBEDDING_MODEL", "").strip(),
            coherence_llm_judge=_flag("COHERENCE_LLM_JUDGE", False),
            coherence_embedding_provider=os.environ.get("COHERENCE_EMBEDDING_PROVIDER", "sentence_transformers").strip().lower(),
            coherence_embedding_url=os.environ.get("COHERENCE_EMBEDDING_URL", "http://localhost:11434").strip(),
            coherence_embedding_timeout_s=float(os.environ.get("COHERENCE_EMBEDDING_TIMEOUT_S", "120")),
            stub=_flag("AI_STUB", False),
        )
