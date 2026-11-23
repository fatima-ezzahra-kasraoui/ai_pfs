"""Points d'accroche de sécurité de l'agent : guards A, B, C, D + moteur de décision (AS-S2-014, 015, 016).

Le flux de l'agent appelle TOUJOURS ces quatre points en mode protégé (aucun chemin du graphe ne les contourne) :

    message entrant      -> Guard A                  -> moteur -> ALLOW / SANITIZE / CONFIRM / BLOCK
    appel d'outil        -> Guard C (+ Guard D)      -> moteur -> décision AVANT toute exécution
    retour d'outil       -> Guard B                  -> moteur -> contenu contrôlé (nettoyé, retiré ou autorisé)
    réponse finale       -> Guard D                  -> moteur

Les guards (A, B, D de Fati ; C dans ``guards/tool_guard.py``) renvoient des ``Verdict`` sans décision ; seul le moteur
(``core/engine.py``) décide. Chaque contrôle produit les verdicts des guards puis UN verdict ``ENGINE`` portant la décision.

**Échec fermé** : si un guard ou le moteur lève une exception, l'étape est BLOCK (jamais ALLOW par défaut) et la cause (type
d'exception uniquement, jamais le contenu) est consignée.

Implémentations : ``PassthroughHooks`` (aucune protection, configuration E1) et ``EngineHooks``.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..core.engine import EngineDecision, PolicyDecisionEngine, SessionState, Stage
from ..guards.tool_guard import ToolGuard
from ..models.verdict import Verdict
from .state import Event

log = logging.getLogger("agentshield.agent")


@dataclass
class HookContext:
    """Contexte d'une exécution partagé par les points d'accroche."""

    correlation_id: str | None
    user_request: str  # demande initiale de l'utilisateur : référence de la cohérence des actions (jamais un contenu d'outil)
    session: SessionState = field(default_factory=SessionState)


@dataclass
class Gate:
    decision: str = "ALLOW"
    events: list[Event] = field(default_factory=list)
    cleaned: str | None = None  # texte nettoyé (SANITIZE)
    arguments: dict[str, Any] | None = None  # arguments nettoyés (SANITIZE d'un appel d'outil)
    engine: EngineDecision | None = None  # décision du moteur (raison, niveau de risque) ; None sans protection ou en échec fermé
    reason: str = ""


class SecurityHooks(Protocol):
    name: str
    protected: bool

    def check_input(self, text: str, ctx: HookContext) -> Gate: ...
    def check_tool_call(self, tool: str, arguments: dict[str, Any], ctx: HookContext) -> Gate: ...
    def check_tool_content(self, tool: str, text: str, ctx: HookContext) -> Gate: ...
    def check_final_response(self, text: str, ctx: HookContext) -> Gate: ...


class PassthroughHooks:
    name = "none"
    protected = False

    def check_input(self, text, ctx):
        return Gate()

    def check_tool_call(self, tool, arguments, ctx):
        return Gate()

    def check_tool_content(self, tool, text, ctx):
        return Gate()

    def check_final_response(self, text, ctx):
        return Gate()


def public_verdict(v: Verdict) -> dict[str, Any]:
    d = v.to_dict()
    d.pop("cleaned", None)  # le texte nettoyé est renvoyé à part ; on ne duplique pas le contenu analysé
    return d


class EngineHooks:
    """Protection par les guards et le moteur de décision. ``enabled`` : sous-ensemble de {A, B, C, D} (ablations du banc)."""

    name = "engine"
    protected = True

    def __init__(self, guards: dict[str, Any], engine: PolicyDecisionEngine, tool_guard: ToolGuard, enabled: set[str] | None = None) -> None:
        self.guards = guards
        self.engine = engine
        self.tool_guard = tool_guard
        self.enabled = enabled if enabled is not None else {"A", "B", "C", "D"}

    def with_enabled(self, enabled: set[str]) -> EngineHooks:
        return EngineHooks(self.guards, self.engine, self.tool_guard, enabled)

    # -- briques communes -------------------------------------------------------------------------------
    @staticmethod
    def _failure(stage: str, module: str, exc: Exception) -> Gate:
        log.error("composant de sécurité indisponible module=%s stage=%s error=%s : blocage par prudence", module, stage, type(exc).__name__)
        reason = f"{module} indisponible ({type(exc).__name__}) : blocage par prudence"
        return Gate("BLOCK", [Event(stage, module, "BLOCK", None, reason)], reason=reason)

    def _decide(self, stage_event: str, stage: Stage, verdicts: list[Verdict], ctx: HookContext) -> tuple[EngineDecision, list[Event]] | Gate:
        started = time.perf_counter()
        try:
            decision = self.engine.decide(stage, verdicts, ctx.session, ctx.correlation_id)
        except Exception as exc:  # noqa: BLE001 - échec fermé
            return self._failure(stage_event, "ENGINE", exc)
        decision.verdict.latency_ms = (time.perf_counter() - started) * 1000
        events = [Event(stage_event, v.module, decision.per_module.get(v.module, "ALLOW"), v.score, v.reason, v.latency_ms or 0.0, public_verdict(v)) for v in verdicts]
        events.append(Event(stage_event, "ENGINE", decision.decision, decision.verdict.score, decision.verdict.reason, decision.verdict.latency_ms, public_verdict(decision.verdict)))
        return decision, events

    def _gate(self, stage_event: str, stage: Stage, verdicts: list[Verdict], ctx: HookContext) -> tuple[Gate, EngineDecision | None]:
        out = self._decide(stage_event, stage, verdicts, ctx)
        if isinstance(out, Gate):
            return out, None
        decision, events = out
        return Gate(decision.decision, events, engine=decision, reason=decision.verdict.reason), decision

    # -- points d'accroche ---------------------------------------------------------------------------------
    def check_input(self, text, ctx):
        if "A" not in self.enabled:
            return Gate()
        try:
            v = self.guards["A"].check({"text": text, "correlation_id": ctx.correlation_id})
        except Exception as exc:  # noqa: BLE001
            return self._failure("input", "A", exc)
        gate, decision = self._gate("input", Stage.INPUT, [v], ctx)
        if decision is not None and decision.decision == "SANITIZE":
            gate.cleaned = v.cleaned
        return gate

    def check_tool_call(self, tool, arguments, ctx):
        verdicts: list[Verdict] = []
        d_verdict: Verdict | None = None
        if "C" in self.enabled:
            try:
                verdicts.append(self.tool_guard.check({"tool": tool, "arguments": arguments, "user_request": ctx.user_request, "correlation_id": ctx.correlation_id}))
            except Exception as exc:  # noqa: BLE001
                return self._failure("tool_call", "C", exc)
        if "D" in self.enabled:
            try:
                d_verdict = self.guards["D"].check({"arguments": arguments, "channel": "tool_arguments", "correlation_id": ctx.correlation_id})
            except Exception as exc:  # noqa: BLE001
                return self._failure("tool_call", "D", exc)
            verdicts.append(d_verdict)
        if not verdicts:
            return Gate()
        gate, decision = self._gate("tool_call", Stage.TOOL_CALL, verdicts, ctx)
        if decision is not None and d_verdict is not None and decision.per_module.get("D") == "SANITIZE":
            try:
                parsed = json.loads(d_verdict.cleaned or "")
                if not isinstance(parsed, dict):
                    raise ValueError("arguments nettoyés inexploitables")
                gate.arguments = parsed
            except ValueError:
                # masquage inexploitable : on n'exécute pas (jamais avec les arguments d'origine)
                gate.decision, gate.reason = "BLOCK", "arguments nettoyés inexploitables : blocage par prudence"
                gate.events.append(Event("tool_call", "ENGINE", "BLOCK", None, gate.reason))
        return gate

    def check_tool_content(self, tool, text, ctx):
        if "B" not in self.enabled:
            return Gate()
        try:
            v = self.guards["B"].check({"text": text, "correlation_id": ctx.correlation_id})
        except Exception as exc:  # noqa: BLE001
            return self._failure("tool_content", "B", exc)
        gate, decision = self._gate("tool_content", Stage.TOOL_RESULT, [v], ctx)
        if decision is not None and decision.decision == "SANITIZE":
            gate.cleaned = v.cleaned
        return gate

    def check_final_response(self, text, ctx):
        if "D" not in self.enabled:
            return Gate()
        try:
            v = self.guards["D"].check({"text": text, "channel": "final_response", "correlation_id": ctx.correlation_id})
        except Exception as exc:  # noqa: BLE001
            return self._failure("final_response", "D", exc)
        gate, decision = self._gate("final_response", Stage.FINAL_RESPONSE, [v], ctx)
        if decision is not None and decision.decision == "SANITIZE":
            gate.cleaned = v.cleaned
        return gate
