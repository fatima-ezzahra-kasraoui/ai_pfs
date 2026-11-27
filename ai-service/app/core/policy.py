"""Chargement et validation de ``config/policy.yaml`` (AS-S2-007).

Le fichier est la source UNIQUE des règles de sécurité : seuils, outils autorisés et risque, paramètres sensibles, décisions de
revue, sorties. Il est validé par Pydantic (clés inconnues refusées, valeurs bornées) ; un fichier invalide est rejeté avec une
erreur claire (``PolicyError``). ``PolicyStore`` le recharge sans redémarrage quand le fichier change.

Sûreté : au démarrage, un fichier invalide empêche l'application de démarrer (échec fermé). Au rechargement, un fichier invalide
est refusé et la DERNIÈRE politique valide reste en vigueur (jamais de politique partielle ni par défaut permissif).
"""
from __future__ import annotations

import hashlib
import logging
import threading
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

log = logging.getLogger("agentshield.policy")

Risk = Literal["low", "medium", "high"]
Action = Literal["ALLOW", "SANITIZE", "CONFIRM", "BLOCK"]
Stage = Literal["input", "tool_call", "tool_result", "final_response"]


class PolicyError(Exception):
    """Politique absente, illisible ou invalide. Le message est destiné à l'opérateur (aucun secret)."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Thresholds(_Strict):
    injection_block: float = Field(ge=0.0, le=1.0)  # score >= injection_block -> BLOCK
    injection_review: float = Field(ge=0.0, le=1.0)  # injection_review <= score < injection_block -> action de revue
    coherence_min: float = Field(ge=0.0, le=1.0)  # similarité action/demande minimale (embeddings, juge LLM)
    # Les similarités lexicales (TF-IDF) ne sont PAS comparables à des cosinus d'embeddings : seuil distinct.
    coherence_min_lexical: float = Field(default=0.10, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _ordered(self) -> Thresholds:
        if self.injection_review > self.injection_block:
            raise ValueError("injection_review doit être inférieur ou égal à injection_block")
        return self


class ToolPolicy(_Strict):
    risk: Risk
    allowed: bool
    require_confirmation: bool = False
    confirm_if_unknown_recipient: bool = False
    check_coherence: bool = True
    allowed_params: tuple[str, ...] | None = None  # None : pas de restriction de paramètres


class ParametersPolicy(_Strict):
    known_recipients: tuple[str, ...] = ()  # adresses exactes
    known_recipient_domains: tuple[str, ...] = ()  # domaines exacts (pas de sous-domaines)
    sensitive_paths: tuple[str, ...] = ()  # motifs fnmatch sur le chemin normalisé (minuscules, absolu, « / »)
    important_files: tuple[str, ...] = ()  # chemins exacts marqués importants

    @field_validator("known_recipients", "known_recipient_domains", "sensitive_paths", "important_files")
    @classmethod
    def _lower(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(x.strip().lower() for x in v)


class ReviewActions(_Strict):
    """Action appliquée quand le score d'un guard est dans la bande [injection_review ; injection_block[."""

    input: Action = "CONFIRM"
    tool_call: Action = "CONFIRM"
    tool_result: Action = "SANITIZE"
    final_response: Action = "SANITIZE"

    @field_validator("input", "tool_call", "tool_result", "final_response")
    @classmethod
    def _not_allow(cls, v: str) -> str:
        if v == "ALLOW":
            raise ValueError("ALLOW n'a pas de sens dans la bande de revue (utiliser SANITIZE, CONFIRM ou BLOCK)")
        return v

    @field_validator("tool_result", "final_response")
    @classmethod
    def _no_confirm_without_action(cls, v: str) -> str:
        if v == "CONFIRM":
            raise ValueError("CONFIRM n'est possible que pour un message entrant ou un appel d'outil (une action à suspendre) ; utiliser SANITIZE ou BLOCK")
        return v


class DecisionsPolicy(_Strict):
    review_action: ReviewActions = ReviewActions()
    on_sensitive_path: Literal["CONFIRM", "BLOCK"] = "CONFIRM"
    on_unknown_recipient: Literal["CONFIRM", "BLOCK"] = "CONFIRM"
    on_incoherent_action: Literal["CONFIRM", "BLOCK"] = "CONFIRM"
    # Hypothèse de conception à valider (R2) : action incohérente après une injection indirecte détectée par le Guard B.
    on_incoherent_after_indirect_injection: Literal["CONFIRM", "BLOCK"] = "BLOCK"
    on_coherence_unavailable: Literal["CONFIRM", "BLOCK"] = "CONFIRM"


class OutputPolicy(_Strict):
    mask_patterns: tuple[str, ...]
    canary_tokens: tuple[str, ...]
    on_secret_detected: Literal["SANITIZE", "BLOCK"]
    on_canary_in_outgoing_tool: Literal["CONFIRM", "BLOCK"]

    @field_validator("canary_tokens")
    @classmethod
    def _non_empty_tokens(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if any(not t.strip() for t in v):
            raise ValueError("un canary token ne peut pas être vide")
        return v


class LoggingPolicy(_Strict):
    mask_excerpts: bool = True


class Policy(_Strict):
    thresholds: Thresholds
    tools: dict[str, ToolPolicy]
    output: OutputPolicy
    parameters: ParametersPolicy = ParametersPolicy()
    decisions: DecisionsPolicy = DecisionsPolicy()
    logging: LoggingPolicy = LoggingPolicy()

    def tool(self, name: str) -> ToolPolicy | None:
        return self.tools.get(name)


_REMOVED_KEYS = {("logging", "db_path"): "la clé logging.db_path a été retirée (AS-S2-007) : la persistance est assurée par le backend ; supprimez-la du fichier"}


def _format_errors(exc: ValidationError) -> str:
    lines = []
    for e in exc.errors():
        where = ".".join(str(p) for p in e["loc"]) or "(racine)"
        lines.append(f"- {where} : {e['msg']}")
    return "\n".join(lines)


def parse_policy(text: str, source: str = "policy.yaml") -> Policy:
    """Valide le contenu d'un fichier de politique. Lève ``PolicyError`` avec un message explicite."""
    try:
        data: Any = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise PolicyError(f"{source} : YAML invalide ({type(exc).__name__})") from exc
    if not isinstance(data, dict):
        raise PolicyError(f"{source} : le fichier doit contenir un objet YAML (clés : thresholds, tools, output…)")
    for (section, key), message in _REMOVED_KEYS.items():
        if isinstance(data.get(section), dict) and key in data[section]:
            raise PolicyError(f"{source} : {message}")
    try:
        return Policy.model_validate(data)
    except ValidationError as exc:
        raise PolicyError(f"{source} invalide :\n{_format_errors(exc)}") from exc


def load_policy(path: str | Path) -> Policy:
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise PolicyError(f"{p} : fichier de politique illisible ({type(exc).__name__})") from exc
    return parse_policy(text, str(p))


class PolicyStore:
    """Politique courante, rechargeable à chaud et sûre entre threads.

    ``get()`` renvoie la politique valide la plus récente : si le fichier a changé (contenu différent), il est relu et validé ;
    s'il est invalide, l'erreur est consignée (``last_error``) et l'ancienne politique reste active.
    """

    def __init__(self, path: str | Path, auto_reload: bool = True) -> None:
        self.path = Path(path)
        self.auto_reload = auto_reload
        self._lock = threading.Lock()
        self._stat: tuple[int, int] | None = None
        self._digest = ""
        self.last_error: str | None = None
        self._policy = self._load_initial()

    @staticmethod
    def _signature(path: Path) -> tuple[int, int] | None:
        try:
            st = path.stat()
        except OSError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def _read(self) -> tuple[Policy, str]:
        text = self.path.read_text(encoding="utf-8")  # OSError traité par l'appelant
        return parse_policy(text, str(self.path)), hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _load_initial(self) -> Policy:
        try:
            policy, digest = self._read()
        except OSError as exc:
            raise PolicyError(f"{self.path} : fichier de politique illisible ({type(exc).__name__})") from exc
        self._stat, self._digest = self._signature(self.path), digest
        return policy

    @property
    def digest(self) -> str:
        return self._digest

    def get(self) -> Policy:
        if self.auto_reload and self._signature(self.path) != self._stat:
            self.reload(raise_on_error=False)
        return self._policy

    def reload(self, raise_on_error: bool = True) -> Policy:
        """Relit le fichier. En cas d'échec, conserve la politique précédente (et lève ``PolicyError`` si demandé)."""
        with self._lock:
            signature = self._signature(self.path)
            try:
                policy, digest = self._read()
            except (OSError, PolicyError) as exc:
                self._stat = signature  # évite de relire en boucle un fichier invalide inchangé
                error = exc if isinstance(exc, PolicyError) else PolicyError(f"{self.path} : fichier de politique illisible ({type(exc).__name__})")
                self.last_error = str(error)
                log.error("rechargement de la politique refusé, politique précédente conservée : %s", str(error).splitlines()[0])
                if raise_on_error:
                    raise error from exc
                return self._policy
            self._stat, self.last_error = signature, None
            if digest != self._digest:
                log.info("politique rechargée (sha256=%s)", digest[:12])
            self._policy, self._digest = policy, digest
            return policy
