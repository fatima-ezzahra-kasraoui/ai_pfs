"""Points d'accroche de sécurité de l'agent (interface vers les guards A–D et le moteur de décision).

Le flux de l'agent appelle TOUJOURS ces quatre points (entrée, appel d'outil, contenu d'outil, réponse finale) :
il n'existe aucun chemin du graphe qui les contourne en mode protégé. Les implémentations :

* ``PassthroughHooks`` : aucune protection (configuration E1, « sans AgentShield ») ;
* ``ReferenceHooks``   : guards A, B, D réels (``app.guards``) + décision de référence TEMPORAIRE, réutilisée
  depuis ``evaluation.sim.pipeline.ReferencePipeline`` (seuils de ``policy.yaml``, Guard C minimal).
  À remplacer par le Guard C et le moteur de décision d'É2 (``app.engine``, Sprint 2) en implémentant ``SecurityHooks``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from .state import Event, worst

SECRET_KINDS = {"api_key", "credit_card", "iban"}  # types masqués dans les arguments d'outil (e-mail/téléphone : destinataires légitimes)


@dataclass
class Gate:
    decision: str = "ALLOW"
    events: list[Event] = field(default_factory=list)
    cleaned: str | None = None  # texte nettoyé (SANITIZE)
    arguments: dict[str, Any] | None = None  # arguments nettoyés (SANITIZE d'un appel d'outil)


class SecurityHooks(Protocol):
    name: str
    protected: bool

    def check_input(self, text: str, correlation_id: str | None) -> Gate: ...
    def check_tool_call(self, tool: str, arguments: dict[str, Any], correlation_id: str | None) -> Gate: ...
    def check_tool_content(self, tool: str, text: str, correlation_id: str | None) -> Gate: ...
    def check_final_response(self, text: str, correlation_id: str | None) -> Gate: ...


class PassthroughHooks:
    name = "none"
    protected = False

    def check_input(self, text, correlation_id):
        return Gate()

    def check_tool_call(self, tool, arguments, correlation_id):
        return Gate()

    def check_tool_content(self, tool, text, correlation_id):
        return Gate()

    def check_final_response(self, text, correlation_id):
        return Gate()


def _public_verdict(v) -> dict[str, Any]:
    d = v.to_dict()
    d.pop("cleaned", None)  # le texte nettoyé est renvoyé à part ; on ne duplique pas le contenu analysé
    return d


class ReferenceHooks:
    """Protection de référence TEMPORAIRE (voir l'en-tête du module). ``enabled`` : sous-ensemble de {A, B, C, D}."""

    name = "reference"
    protected = True

    def __init__(self, guards: dict[str, Any], pipeline, enabled: set[str] | None = None) -> None:
        self.guards = guards
        self.pipeline = pipeline  # ReferencePipeline : seuils, politique, décision score -> action
        self.enabled = enabled if enabled is not None else {"A", "B", "C", "D"}

    def with_enabled(self, enabled: set[str]) -> ReferenceHooks:
        return ReferenceHooks(self.guards, self.pipeline, enabled)

    def _verdict_event(self, stage: str, module: str, decision: str, v) -> Event:
        return Event(stage, module, decision, v.score, v.reason, v.latency_ms or 0.0, _public_verdict(v))

    def check_input(self, text, correlation_id):
        if "A" not in self.enabled:
            return Gate()
        v = self.guards["A"].check({"text": text, "correlation_id": correlation_id})
        d = self.pipeline._score_decision(v.score)
        return Gate(d, [self._verdict_event("input", "A", d, v)])

    def check_tool_content(self, tool, text, correlation_id):
        if "B" not in self.enabled:
            return Gate()
        v = self.guards["B"].check({"text": text, "correlation_id": correlation_id})
        d = self.pipeline._score_decision(v.score)
        d = "SANITIZE" if d == "CONFIRM" else d  # contenu externe : on nettoie plutôt que d'interrompre
        return Gate(d, [self._verdict_event("tool_content", "B", d, v)], cleaned=v.cleaned if d == "SANITIZE" else None)

    def check_tool_call(self, tool, arguments, correlation_id):
        events: list[Event] = []
        decisions: list[str] = []
        cleaned_args: dict[str, Any] | None = None
        if "C" in self.enabled:
            d, why = self.pipeline._tool_decision(tool, arguments)
            events.append(Event("tool_call", "C", d, None, why))
            decisions.append(d)
        if "D" in self.enabled:
            v = self.guards["D"].check({"arguments": arguments, "channel": "tool_arguments", "correlation_id": correlation_id})
            kinds = set(v.metadata.get("kinds", []))
            if v.metadata.get("canary"):
                d = "BLOCK"
            elif kinds & SECRET_KINDS:
                d = "SANITIZE"
                try:
                    parsed = json.loads(v.cleaned or "")
                    cleaned_args = parsed if isinstance(parsed, dict) else None
                except ValueError:
                    cleaned_args = None
                if cleaned_args is None:
                    d = "BLOCK"  # masquage inexploitable : par prudence on n'exécute pas
            else:
                d = "ALLOW"
            events.append(self._verdict_event("tool_call", "D", d, v))
            decisions.append(d)
        return Gate(worst(decisions), events, arguments=cleaned_args)

    def check_final_response(self, text, correlation_id):
        if "D" not in self.enabled:
            return Gate()
        v = self.guards["D"].check({"text": text, "channel": "final_response", "correlation_id": correlation_id})
        d = "SANITIZE" if v.metadata.get("kinds") else "ALLOW"
        return Gate(d, [self._verdict_event("final_response", "D", d, v)], cleaned=v.cleaned if d == "SANITIZE" else None)
