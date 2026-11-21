"""Configuration du LLM, lue dans l'environnement. Aucun secret en dur, aucune valeur par défaut de clé."""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from .errors import LLMConfigError

PROVIDERS = ("mock", "anthropic", "openai_compatible")


def _num(env: Mapping[str, str], key: str, default: float, cast=float):
    raw = env.get(key, "").strip()
    if not raw:
        return default
    try:
        return cast(raw)
    except ValueError as exc:
        raise LLMConfigError(f"{key} doit être numérique") from exc


@dataclass(frozen=True)
class LLMConfig:
    """``provider="mock"`` (défaut) : simulation déterministe, aucun appel réseau, aucune clé."""

    provider: str = "mock"
    model: str = ""
    api_key: str = field(default="", repr=False)  # jamais affiché (repr, journaux, /health)
    base_url: str = ""
    timeout_s: float = 30.0
    max_tokens: int = 1024
    temperature: float = 0.0
    max_retries: int = 1

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> LLMConfig:
        e = os.environ if env is None else env
        return cls(
            provider=e.get("LLM_PROVIDER", "mock").strip().lower() or "mock",
            model=e.get("LLM_MODEL", "").strip(),
            api_key=e.get("LLM_API_KEY", "").strip(),
            base_url=e.get("LLM_BASE_URL", "").strip(),
            timeout_s=_num(e, "LLM_TIMEOUT_S", 30.0),
            max_tokens=_num(e, "LLM_MAX_TOKENS", 1024, int),
            temperature=_num(e, "LLM_TEMPERATURE", 0.0),
            max_retries=_num(e, "LLM_MAX_RETRIES", 1, int),
        )

    def validate(self) -> None:
        """Lève ``LLMConfigError`` si la configuration est inutilisable (échec fermé, sans valeur inventée)."""
        if self.provider not in PROVIDERS:
            raise LLMConfigError(f"LLM_PROVIDER inconnu : {self.provider!r} (valeurs : {', '.join(PROVIDERS)})")
        if self.timeout_s <= 0 or self.max_tokens <= 0 or self.max_retries < 0:
            raise LLMConfigError("LLM_TIMEOUT_S, LLM_MAX_TOKENS doivent être > 0 et LLM_MAX_RETRIES >= 0")
        if self.provider == "mock":
            return
        if not self.model:
            raise LLMConfigError("LLM_MODEL est requis pour un fournisseur réel")
        if self.provider == "anthropic" and not self.api_key:
            raise LLMConfigError("LLM_API_KEY est requis pour le fournisseur anthropic")
        if self.provider == "openai_compatible" and not self.base_url:
            raise LLMConfigError("LLM_BASE_URL est requis pour le fournisseur openai_compatible")

    def public(self) -> dict[str, object]:
        """Vue sans secret, exposable (santé, journal)."""
        return {"provider": self.provider, "model": self.model or None, "simulated": self.provider == "mock", "apiKeyConfigured": bool(self.api_key)}
