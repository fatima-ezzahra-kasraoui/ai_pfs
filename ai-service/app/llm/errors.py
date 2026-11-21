"""Erreurs de la couche LLM. Aucun message ne contient de clé API ni le corps brut d'une réponse."""
from __future__ import annotations


class LLMError(Exception):
    """Erreur de base de la couche LLM."""


class LLMConfigError(LLMError):
    """Configuration invalide ou incomplète (fournisseur inconnu, clé ou modèle manquant)."""


class LLMTimeoutError(LLMError):
    """Le fournisseur n'a pas répondu dans le délai imparti."""


class LLMProviderError(LLMError):
    """Réponse d'erreur du fournisseur (HTTP >= 400) ou erreur réseau."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class LLMResponseError(LLMError):
    """Réponse du fournisseur inexploitable (JSON invalide, structure inattendue)."""
