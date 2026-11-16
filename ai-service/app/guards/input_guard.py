"""Guard A — Input Guard : détection d'injection directe et de jailbreak (F02).

Pipeline : normalisation Unicode -> règles FR/EN -> classifieur (par morceaux, score
maximal) -> fusion. Le guard ne renvoie **jamais** de décision, seulement un
``Verdict`` : la décision appartient au moteur de décision (policy.yaml).

Si aucun classifieur n'est disponible, le guard reste opérationnel en mode dégradé
(règles seules) et le signale via ``Verdict.degraded``.
"""
from __future__ import annotations

import time
from typing import Any

from ..core.text import chunk_text, despace, fold, normalize
from ..models.verdict import AttackType, Guard, Verdict, risk_from_score
from .classifier import Classifier
from .rules import RuleHit, combine, match_rules

# Un signal d'évasion (caractères invisibles) sans règle déclenchée reste faible.
EVASION_ONLY_SCORE = 0.20
EVASION_BONUS = 0.10
# Seuil d'étiquetage de l'attackType uniquement (pas une décision).
LABEL_THRESHOLD = 0.50


class InputGuard(Guard):
    module = "A"

    def __init__(
        self,
        classifier: Classifier | None = None,
        *,
        max_chunk_chars: int = 1200,
        overlap: int = 150,
        use_rules: bool = True,
    ) -> None:
        self.classifier = classifier
        self.max_chunk_chars = max_chunk_chars
        self.overlap = overlap
        self.use_rules = use_rules

    @property
    def degraded(self) -> bool:
        return self.classifier is None

    def check(self, context: dict[str, Any]) -> Verdict:
        started = time.perf_counter()
        raw = str(context.get("text") or context.get("message") or "")
        correlation_id = context.get("correlation_id") or context.get("correlationId")

        normalized, evasion = normalize(raw)
        folded = fold(normalized)

        hits: list[RuleHit] = []
        if self.use_rules:
            hits = match_rules(folded)
            spaced = despace(raw)
            if spaced != raw:  # mot écrit lettre par lettre : on analyse aussi la version recollée
                known = {h.rule_id for h in hits}
                hits += [h for h in match_rules(fold(normalize(spaced)[0])) if h.rule_id not in known]
        rule_score = combine([h.weight for h in hits])
        if hits and (evasion["invisible"] or evasion["homoglyphs"]):
            rule_score = min(0.98, rule_score + EVASION_BONUS)

        clf_score = 0.0
        chunks = chunk_text(normalized, self.max_chunk_chars, self.overlap)
        if self.classifier is not None and chunks:
            clf_score = max(self.classifier.predict_proba(chunks))

        score = max(rule_score, clf_score)
        if not hits and (evasion["invisible"] or evasion["homoglyphs"]) and score < EVASION_ONLY_SCORE:
            score = EVASION_ONLY_SCORE

        attack_type = AttackType.DIRECT_INJECTION if score >= LABEL_THRESHOLD else AttackType.NONE
        reason = self._reason(hits, clf_score, evasion, len(chunks))

        return Verdict(
            module=self.module,
            score=score,
            attack_type=attack_type.value,
            reason=reason,
            risk_level=risk_from_score(score).value,
            correlation_id=correlation_id,
            degraded=self.degraded,
            latency_ms=(time.perf_counter() - started) * 1000,
            metadata={
                "rules": [h.rule_id for h in hits],
                "ruleScore": round(rule_score, 4),
                "classifierScore": round(clf_score, 4) if self.classifier else None,
                "classifier": getattr(self.classifier, "name", None),
                "chunks": len(chunks),
                "evasion": evasion,
            },
        )

    def _reason(self, hits: list[RuleHit], clf_score: float, evasion: dict[str, int], n_chunks: int) -> str:
        parts: list[str] = []
        if hits:
            cats = sorted({h.category for h in hits})
            parts.append(f"règles déclenchées : {', '.join(h.rule_id for h in hits)} ({', '.join(cats)})")
        if self.classifier is not None:
            parts.append(f"classifieur {getattr(self.classifier, 'name', '?')} : {clf_score:.2f} sur {n_chunks} morceau(x)")
        if evasion["invisible"]:
            parts.append(f"{evasion['invisible']} caractère(s) invisible(s) retiré(s)")
        if evasion["homoglyphs"]:
            parts.append(f"{evasion['homoglyphs']} homoglyphe(s) normalisé(s)")
        if self.degraded:
            parts.append("mode dégradé : règles seules")
        return " ; ".join(parts) if parts else "aucun signal d'injection"
