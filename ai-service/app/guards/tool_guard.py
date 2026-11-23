"""Guard C : contrôle de chaque appel d'outil AVANT exécution (AS-S2-008, 009, 010).

Comme tous les guards, il ne décide pas : il renvoie un ``Verdict`` (``decision = None``) dont ``metadata["findings"]`` liste ses
constats ; le moteur (``core/engine.py``) applique la politique. Constats (``kind``) :

===========================  ==============  =====================================================================
kind                         classe          déclenchement
===========================  ==============  =====================================================================
``tool_not_allowed``         interdiction    outil absent de la politique ou ``allowed: false``
``invalid_arguments``        interdiction    arguments qui ne sont pas un objet
``unexpected_parameter``     interdiction    paramètre hors de ``allowed_params``
``path_bypass``              interdiction    ``..``, octet nul, séparateur ou point encodé dans un chemin
``canary_in_arguments``      interdiction    canary token dans les arguments (normalisés : invisibles, homoglyphes, espaces)
``requires_confirmation``    confirmation    ``require_confirmation: true`` (ex. ``delete_file``)
``unknown_recipient``        confirmation    destinataire hors ``known_recipients`` / ``known_recipient_domains``
``sensitive_path``           confirmation    chemin sensible (``sensitive_paths``) ou fichier important (``important_files``)
``action_incoherent``        confirmation    similarité action/demande < seuil (``coherence_min`` ou ``_lexical``)
``coherence_unavailable``    confirmation    aucune mesure de cohérence disponible (jamais présumée « bonne »)
===========================  ==============  =====================================================================

``score`` : 1,0 pour une interdiction ; ``thresholds.injection_review`` pour une condition de confirmation (valeur minimale qui
reproduit le constat sous les seuils de la politique) ; 0,0 sinon. ``risk_level`` vient de la politique (risque de l'outil), pas du
score : les deux champs restent distincts. Aucune valeur d'argument n'est recopiée dans le verdict (les raisons citent les règles).
"""
from __future__ import annotations

import fnmatch
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

from ..core.policy import Policy, PolicyStore
from ..core.text import despace, fold, normalize, strip_invisible
from ..models.verdict import AttackType, Guard, Verdict
from .coherence import CoherenceChecker, TfidfCoherence, describe_action

PROHIBITION_KINDS = frozenset({"tool_not_allowed", "invalid_arguments", "unexpected_parameter", "path_bypass", "canary_in_arguments"})
_ENCODED_BYPASS = re.compile(r"%(?:2e|2f|5c|00)", re.IGNORECASE)
_ADDRESS = re.compile(r"^[a-z0-9._%+-]{1,64}@([a-z0-9-]+(?:\.[a-z0-9-]+)+)$")
MAX_DEPTH = 6
MAX_STRINGS = 500


@dataclass(frozen=True)
class Finding:
    kind: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "detail": self.detail}


def _strings(value: Any, depth: int = 0, out: list[str] | None = None) -> list[str]:
    """Toutes les chaînes (clés comprises) d'une structure d'arguments, bornées en profondeur et en nombre."""
    out = [] if out is None else out
    if len(out) >= MAX_STRINGS or depth > MAX_DEPTH:
        return out
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for k, v in value.items():
            _strings(str(k), depth + 1, out)
            _strings(v, depth + 1, out)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _strings(v, depth + 1, out)
    elif value is not None:
        out.append(str(value))
    return out


def _canonical(text: str) -> str:
    return despace(fold(normalize(text)[0])).replace(" ", "")


def normalize_path(raw: str) -> tuple[str, list[str]]:
    """Chemin canonique (absolu, minuscules, « / », sans point/espace final) et liste des tentatives de contournement détectées."""
    problems: list[str] = []
    if _ENCODED_BYPASS.search(raw):
        problems.append("séparateur, point ou octet nul encodé")
    text = raw
    for _ in range(3):  # décodage répété : « %252e » -> « %2e » -> « . »
        decoded = unquote(text)
        if decoded == text:
            break
        text = decoded
    text, _ = strip_invisible(unicodedata.normalize("NFKC", text))
    if "\x00" in text:
        problems.append("octet nul")
    text = text.replace("\\", "/")
    raw_segments = text.split("/")
    segments = [s.rstrip(". ") if s not in {".", ".."} else s for s in raw_segments]
    if ".." in segments:
        problems.append("remontée de répertoire « .. »")
    elif any(s not in {"", ".", ".."} and not s.strip(". ") for s in raw_segments):
        problems.append("segment composé uniquement de points ou d'espaces")
    kept = [s for s in segments if s not in {"", "."}]
    return "/" + "/".join(kept).lower(), problems


class ToolGuard(Guard):
    module = "C"

    def __init__(self, policy: PolicyStore | Policy, coherence: CoherenceChecker | None = None) -> None:
        self._policy = policy
        self.coherence: CoherenceChecker = coherence or TfidfCoherence()

    @property
    def degraded(self) -> bool:
        """True si aucune mesure de cohérence SÉMANTIQUE n'est configurée (repli lexical seul)."""
        checkers = getattr(self.coherence, "checkers", (self.coherence,))
        return not any(getattr(c, "semantic", False) for c in checkers)

    def _current(self) -> Policy:
        return self._policy.get() if isinstance(self._policy, PolicyStore) else self._policy

    # -- règles ---------------------------------------------------------------------------------------
    def _parameter_findings(self, policy: Policy, tool: str, args: dict[str, Any]) -> list[Finding]:
        findings: list[Finding] = []
        spec = policy.tool(tool)
        if spec is not None and spec.allowed_params is not None:
            unexpected = [k for k in args if k not in spec.allowed_params]
            if unexpected:
                # Le NOM des paramètres est contrôlé par l'appelant (il peut contenir un secret) : on n'en donne que le nombre.
                findings.append(Finding("unexpected_parameter", f"{len(unexpected)} paramètre(s) non autorisé(s) pour {tool} (hors liste blanche de la politique)"))
        tokens = policy.output.canary_tokens
        if tokens and any(canary and canary in _canonical(s) for s in _strings(args) for canary in map(_canonical, tokens)):
            findings.append(Finding("canary_in_arguments", "canary token dans les arguments de l'outil (fuite avérée)"))
        path = args.get("path")
        if isinstance(path, str):
            normalized, problems = normalize_path(path)
            if problems:
                findings.append(Finding("path_bypass", f"tentative de contournement du chemin : {', '.join(problems)}"))
            elif self._is_sensitive(policy, normalized):
                findings.append(Finding("sensitive_path", "chemin sensible ou fichier marqué important"))
        if spec is not None and spec.confirm_if_unknown_recipient:
            reason = self._recipient_problem(policy, args.get("to"))
            if reason:
                findings.append(Finding("unknown_recipient", reason))
        return findings

    @staticmethod
    def _is_sensitive(policy: Policy, normalized_path: str) -> bool:
        params = policy.parameters
        return normalized_path in params.important_files or any(fnmatch.fnmatchcase(normalized_path, pat) for pat in params.sensitive_paths)

    @staticmethod
    def _recipient_problem(policy: Policy, to: Any) -> str | None:
        if not isinstance(to, str) or not to.strip():
            return "destinataire absent ou invalide"
        address = to.strip().lower()
        if not address.isascii():
            return "destinataire non ASCII (risque d'homographe) : considéré comme inconnu"
        match = _ADDRESS.match(address)
        if match is None:
            return "destinataire non reconnaissable comme une adresse unique : considéré comme inconnu"
        known = policy.parameters
        if address in known.known_recipients or match.group(1) in known.known_recipient_domains:
            return None
        return "destinataire inconnu (hors liste des destinataires connus)"

    def _coherence(self, policy: Policy, tool: str, args: dict[str, Any], request: str) -> tuple[list[Finding], dict[str, Any]]:
        result = self.coherence.compare(request, describe_action(tool, args))
        threshold = policy.thresholds.coherence_min if result.semantic else policy.thresholds.coherence_min_lexical
        info: dict[str, Any] = {"score": None if result.score is None else round(result.score, 4), "method": result.method, "semantic": result.semantic, "threshold": threshold}
        if result.score is None:
            info["coherent"] = None
            return [Finding("coherence_unavailable", f"cohérence invérifiable : {result.detail}")], info
        info["coherent"] = result.score >= threshold
        if info["coherent"]:
            return [], info
        kind = "lexicale (non sémantique)" if not result.semantic else result.method
        return [Finding("action_incoherent", f"action incohérente avec la demande de l'utilisateur (similarité {kind} {result.score:.2f} < {threshold:.2f})")], info

    # -- API Guard -------------------------------------------------------------------------------------
    def check(self, context: dict[str, Any]) -> Verdict:
        started = time.perf_counter()
        policy = self._current()
        tool = str(context.get("tool") or "")
        args = context.get("arguments")
        request = context.get("user_request")
        findings: list[Finding] = []
        coherence_info: dict[str, Any] | None = None
        spec = policy.tool(tool)
        if spec is None or not spec.allowed:
            findings.append(Finding("tool_not_allowed", "outil non autorisé par la politique" if spec else "outil inconnu (hors liste blanche)"))
        elif not isinstance(args, dict):
            findings.append(Finding("invalid_arguments", "les arguments d'un outil doivent être un objet"))
        else:
            findings += self._parameter_findings(policy, tool, args)
            if spec.require_confirmation:
                findings.append(Finding("requires_confirmation", f"outil à risque {spec.risk} : confirmation exigée par la politique"))
            if spec.check_coherence and isinstance(request, str) and request.strip() and not any(f.kind in PROHIBITION_KINDS for f in findings):
                extra, coherence_info = self._coherence(policy, tool, args, request)
                findings += extra
        prohibited = any(f.kind in PROHIBITION_KINDS for f in findings)
        score = 1.0 if prohibited else (policy.thresholds.injection_review if findings else 0.0)
        degraded = bool(coherence_info and not coherence_info["semantic"])
        metadata: dict[str, Any] = {"tool": tool, "toolRisk": spec.risk if spec else "high", "findings": [f.to_dict() for f in findings]}
        if coherence_info is not None:
            metadata["coherence"] = coherence_info
        return Verdict(
            module="C", score=score,
            attack_type=(AttackType.TOOL_ABUSE if findings else AttackType.NONE).value,
            reason="; ".join(f.detail for f in findings) if findings else "outil autorisé, paramètres conformes",
            risk_level=spec.risk if spec else "high",
            correlation_id=context.get("correlation_id") or context.get("correlationId"),
            degraded=degraded, latency_ms=(time.perf_counter() - started) * 1000, metadata=metadata,
        )
