"""Policy Decision Engine (AS-S2-011) : agrège les verdicts des guards et décide ALLOW / SANITIZE / CONFIRM / BLOCK.

Emplacement : ``core/engine.py`` (livrable du plan Agile). C'est le SEUL moteur : le répertoire ``app/engine/`` ne contient qu'un
README de renvoi. Les guards ne décident jamais ; seul ce module produit une décision, à partir de ``config/policy.yaml``.

**Ordre de priorité** (reconstitué d'après le plan Agile ; le §10 du dossier de conception n'était pas disponible, voir le rapport) :

1. **Interdiction explicite** (P1) : outil hors liste blanche, paramètre non autorisé, contournement de chemin, canary dans un outil
   sortant. Décision BLOCK, **jamais contournée par un score faible**.
2. **Confirmation** (P2) : outil à confirmation obligatoire, destinataire inconnu, chemin sensible, action incohérente, cohérence
   invérifiable. Décision CONFIRM (ou BLOCK si la politique l'impose).
3. **Seuils** (P3) : score ≥ ``injection_block`` → BLOCK ; ``injection_review`` ≤ score < ``injection_block`` → action de revue de
   l'étape (``decisions.review_action``) ; secrets/canary en sortie → ``output.on_secret_detected`` (SANITIZE).
4. **ALLOW** quand aucune règle ne s'applique.

**Agrégation** : la décision finale est la plus sévère des contributions (BLOCK > CONFIRM > SANITIZE > ALLOW) ; à sévérité égale, la
règle de priorité la plus haute (P1 avant P2 avant P3) fournit la raison. ``score`` (le plus élevé des scores reçus) et ``risk_level``
(le plus élevé des niveaux de risque : outil visé, ou score selon les seuils de la politique) restent deux champs distincts.

**Règle d'escalade** (hypothèse de conception liée à R2, À VALIDER) : une action incohérente avec la demande passe en BLOCK si le Guard B
a détecté une injection indirecte plus tôt dans la session, sinon en CONFIRM (``decisions.on_incoherent_*``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..models.verdict import AttackType, RiskLevel, Verdict
from .policy import Policy, PolicyStore

SEVERITY = {"ALLOW": 0, "SANITIZE": 1, "CONFIRM": 2, "BLOCK": 3}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def worst(decisions: list[str]) -> str:
    return max(decisions, key=lambda d: SEVERITY[d]) if decisions else "ALLOW"


class Stage(str, Enum):
    INPUT = "input"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FINAL_RESPONSE = "final_response"


@dataclass
class SessionState:
    """État de session consulté (et mis à jour) par le moteur : une instance par exécution de l'agent."""

    indirect_injection_detected: bool = False


@dataclass(frozen=True)
class Contribution:
    module: str
    decision: str
    rule: str  # identifiant stable de la règle (voir la table dans docs/ai-service-engine.md)
    reason: str
    priority: int  # 1 interdiction, 2 confirmation, 3 seuil / sortie, 4 autorisation
    rules: tuple[str, ...] = ()  # toutes les règles de même sévérité qui s'appliquent (audit) ; ``rule`` est la plus prioritaire


@dataclass(frozen=True)
class EngineDecision:
    decision: str
    stage: str
    rule: str
    reason: str
    contributions: tuple[Contribution, ...]
    verdict: Verdict  # Verdict du module ENGINE (decision renseignée)
    escalated: bool = False
    canary: bool = False  # un canary a été signalé (fuite avérée) parmi les verdicts
    per_module: dict[str, str] = field(default_factory=dict)  # module -> décision de sa contribution


def _level_from_score(policy: Policy, score: float) -> str:
    if score >= policy.thresholds.injection_block:
        return RiskLevel.HIGH.value
    if score >= policy.thresholds.injection_review:
        return RiskLevel.MEDIUM.value
    return RiskLevel.LOW.value


class PolicyDecisionEngine:
    def __init__(self, policy: PolicyStore | Policy) -> None:
        self._policy = policy

    def _current(self) -> Policy:
        return self._policy.get() if isinstance(self._policy, PolicyStore) else self._policy

    @property
    def policy_digest(self) -> str | None:
        return self._policy.digest[:12] if isinstance(self._policy, PolicyStore) else None

    # -- règles par module -----------------------------------------------------------------------------
    @staticmethod
    def _class_of(decision: str) -> int:
        return 1 if decision == "BLOCK" else 2

    def _tool_call(self, policy: Policy, v: Verdict, session: SessionState) -> tuple[Contribution, bool]:
        """Guard C : applique la politique à chaque constat. Retourne (contribution, escalade)."""
        d = policy.decisions
        out_canary = policy.output.on_canary_in_outgoing_tool
        mapping: dict[str, tuple[str, int, str]] = {
            "tool_not_allowed": ("BLOCK", 1, "P1.tool_not_allowed"),
            "invalid_arguments": ("BLOCK", 1, "P1.invalid_arguments"),
            "unexpected_parameter": ("BLOCK", 1, "P1.unexpected_parameter"),
            "path_bypass": ("BLOCK", 1, "P1.path_bypass"),
            "canary_in_arguments": (out_canary, self._class_of(out_canary), "P1.canary_outgoing" if out_canary == "BLOCK" else "P2.canary_outgoing"),
            "requires_confirmation": ("CONFIRM", 2, "P2.requires_confirmation"),
            "unknown_recipient": (d.on_unknown_recipient, self._class_of(d.on_unknown_recipient), "P2.unknown_recipient" if d.on_unknown_recipient == "CONFIRM" else "P1.unknown_recipient"),
            "sensitive_path": (d.on_sensitive_path, self._class_of(d.on_sensitive_path), "P2.sensitive_path" if d.on_sensitive_path == "CONFIRM" else "P1.sensitive_path"),
            "coherence_unavailable": (d.on_coherence_unavailable, self._class_of(d.on_coherence_unavailable), "P2.coherence_unavailable"),
        }
        cands: list[Contribution] = []
        for finding in v.metadata.get("findings", []):
            kind = finding.get("kind", "")
            if kind == "action_incoherent":
                decision = d.on_incoherent_after_indirect_injection if session.indirect_injection_detected else d.on_incoherent_action
                if decision == "BLOCK":
                    rule = "P1.incoherent_after_injection" if session.indirect_injection_detected else "P1.incoherent_action"
                else:
                    rule = "P2.incoherent_action"
                cands.append(Contribution("C", decision, rule, finding.get("detail", ""), self._class_of(decision)))
            elif kind in mapping:
                decision, priority, rule = mapping[kind]
                cands.append(Contribution("C", decision, rule, finding.get("detail", ""), priority))
            else:  # constat inconnu : par prudence, confirmation (jamais ALLOW silencieux)
                cands.append(Contribution("C", "CONFIRM", "P2.unknown_finding", f"constat inconnu du Guard C : {kind}", 2))
        if not cands:
            return Contribution("C", "ALLOW", "A.tool_ok", v.reason, 4, ("A.tool_ok",)), False
        top = max(SEVERITY[c.decision] for c in cands)
        tied = sorted((c for c in cands if SEVERITY[c.decision] == top), key=lambda c: c.priority)  # tri stable : ordre des constats conservé
        best = tied[0]
        reason = "; ".join(dict.fromkeys(c.reason for c in tied))
        escalated = any(c.rule == "P1.incoherent_after_injection" for c in tied)
        return Contribution("C", best.decision, best.rule, reason, best.priority, tuple(dict.fromkeys(c.rule for c in tied))), escalated

    def _detector(self, policy: Policy, v: Verdict, stage: Stage) -> Contribution:
        """Guards A et B (score d'injection) : seuils, puis action de revue de l'étape."""
        th = policy.thresholds
        if v.score >= th.injection_block:
            return Contribution(v.module, "BLOCK", "T.block", f"score {v.score:.2f} ≥ seuil de blocage {th.injection_block:.2f} : {v.reason}", 3)
        if v.score >= th.injection_review:
            action = getattr(policy.decisions.review_action, stage.value if stage is not Stage.TOOL_RESULT else "tool_result")
            return Contribution(v.module, action, f"T.review.{action.lower()}", f"score {v.score:.2f} dans la bande de revue [{th.injection_review:.2f} ; {th.injection_block:.2f}[ : {v.reason}", 3)
        return Contribution(v.module, "ALLOW", "A.below_review", f"score {v.score:.2f} sous le seuil de revue", 4)

    def _output(self, policy: Policy, v: Verdict, stage: Stage) -> tuple[Contribution, bool]:
        """Guard D : canary et secrets, selon le canal (arguments d'un outil sortant ou réponse finale)."""
        canary = bool(v.metadata.get("canary"))
        kinds = set(v.metadata.get("kinds", []))
        out = policy.output
        if stage is Stage.TOOL_CALL:
            if canary:
                return Contribution("D", out.on_canary_in_outgoing_tool, "P1.canary_outgoing" if out.on_canary_in_outgoing_tool == "BLOCK" else "P2.canary_outgoing", "canary token dans les arguments d'un outil sortant (fuite avérée)", self._class_of(out.on_canary_in_outgoing_tool)), True
            masked = kinds & set(out.mask_patterns)
            if masked:
                return Contribution("D", out.on_secret_detected, "S.secret_masked", f"secret dans les arguments d'un outil ({', '.join(sorted(masked))})", 3), False
            return Contribution("D", "ALLOW", "A.args_clean", "aucun secret dans les arguments", 4), False
        if canary or kinds:
            note = "canary signalé : fuite avérée ; " if canary else ""
            return Contribution("D", out.on_secret_detected, "S.canary_in_response" if canary else "S.secret_masked", f"{note}donnée sensible dans la sortie ({', '.join(sorted(kinds)) or 'canary'})", 3), canary
        return Contribution("D", "ALLOW", "A.output_clean", "aucune donnée sensible", 4), False

    # -- décision ---------------------------------------------------------------------------------------
    def decide(self, stage: Stage, verdicts: list[Verdict], session: SessionState | None = None, correlation_id: str | None = None) -> EngineDecision:
        """Décision pour une étape. ``session`` est mis à jour : un verdict B de revue ou plus lève ``indirect_injection_detected``."""
        policy = self._current()
        session = session if session is not None else SessionState()
        contributions: list[Contribution] = []
        escalated = canary = False
        for v in verdicts:
            if v.module == "C":
                c, esc = self._tool_call(policy, v, session)
                escalated = escalated or esc
            elif v.module == "D":
                c, can = self._output(policy, v, stage)
                canary = canary or can
            else:  # A, B (et tout détecteur à score) : seuils
                c = self._detector(policy, v, stage)
                if v.module == "B" and v.score >= policy.thresholds.injection_review:
                    session.indirect_injection_detected = True
            contributions.append(c)
        if contributions:
            winner = min((c for c in contributions if SEVERITY[c.decision] == max(SEVERITY[x.decision] for x in contributions)), key=lambda c: c.priority)
        else:
            winner = Contribution("ENGINE", "ALLOW", "A.no_verdict", "aucun contrôle actif pour cette étape", 4)
        max_score = max((v.score for v in verdicts), default=0.0)
        risk = max(
            [v.risk_level for v in verdicts] + [_level_from_score(policy, v.score) for v in verdicts if v.module in {"A", "B", "D"}] or ["low"],
            key=lambda r: RISK_ORDER[r],
        )
        attack = next((v.attack_type for c in contributions if c is winner for v in verdicts if v.module == c.module and v.attack_type != "none"), None)
        attack = attack or next((v.attack_type for v in verdicts if v.attack_type != "none"), AttackType.NONE.value)
        flags = [f"rule={winner.rule}"] + (["canary"] if canary else []) + (["escalated"] if escalated else [])
        engine_verdict = Verdict(
            module="ENGINE", score=max_score, attack_type=attack, reason=f"[{winner.rule}] {winner.reason}", risk_level=risk, decision=winner.decision,
            correlation_id=correlation_id, degraded=any(v.degraded for v in verdicts),
            metadata={
                "stage": stage.value, "rule": winner.rule, "escalated": escalated, "canary": canary, "flags": flags,
                "contributions": [{"module": c.module, "decision": c.decision, "rule": c.rule, "rules": list(c.rules or (c.rule,))} for c in contributions],
                **({"policy": self.policy_digest} if self.policy_digest else {}),
            },
        )
        per_module: dict[str, str] = {}
        for c in contributions:
            per_module[c.module] = worst([per_module.get(c.module, "ALLOW"), c.decision])
        return EngineDecision(winner.decision, stage.value, winner.rule, winner.reason, tuple(contributions), engine_verdict, escalated, canary, per_module)


__all__: list[Any] = ["Contribution", "EngineDecision", "PolicyDecisionEngine", "SEVERITY", "SessionState", "Stage", "worst"]
