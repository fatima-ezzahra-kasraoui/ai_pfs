"""Guard D — Output & Data Guard : fuite de données (F05).

Détecte clés API, IBAN, cartes bancaires, canary tokens, e-mails, téléphones (regex avec
validation Luhn / mod 97 pour limiter les faux positifs) et, si Presidio est
installé, noms de personnes. Produit un texte masqué partiellement (``sk-****``).

Règles de confidentialité :
* le verdict ne contient JAMAIS la valeur brute d'un secret (ni dans ``reason``, ni dans
  ``metadata``), seulement son type et sa position ;
* le texte masqué est fourni dans ``Verdict.cleaned``.
La décision (SANITIZE pour une réponse, BLOCK si le canary part dans un outil sortant)
est prise par le moteur à partir de ``metadata["canary"]`` et du canal analysé.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..models.verdict import AttackType, Guard, Verdict, risk_from_score

DEFAULT_CANARIES = ("sk-FAKE-1234",)

# priorité (plus petit = prioritaire) lors du chevauchement de deux détections
PRIORITY = {"canary": 0, "api_key": 1, "credit_card": 2, "iban": 3, "email": 4, "phone": 5, "person": 6}
SCORES = {"canary": 1.0, "api_key": 0.95, "credit_card": 0.90, "iban": 0.90, "email": 0.60, "phone": 0.60, "person": 0.50}


# ----------------------------------------------------------------------------- validations
def luhn_valid(digits: str) -> bool:
    if not 13 <= len(digits) <= 19 or not digits.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def iban_valid(value: str) -> bool:
    iban = re.sub(r"\s+", "", value).upper()
    if not 15 <= len(iban) <= 34 or not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]+", iban):
        return False
    rearranged = iban[4:] + iban[:4]
    numeric = "".join(str(int(c, 36)) for c in rearranged)
    return int(numeric) % 97 == 1


# ----------------------------------------------------------------------------- détections
@dataclass(frozen=True)
class Finding:
    kind: str
    start: int
    end: int


class PersonDetector(Protocol):
    def detect(self, text: str) -> list[Finding]: ...


_API_KEY_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{16,}"),
)
_KEY_VALUE = re.compile(
    r"(?i)\b(?:api[_ -]?key|apikey|secret(?:[_ -]?key)?|access[_ -]?token|token|passwd|password|mot\s+de\s+passe|cl[eé]\s+api)\s*[:=]\s*[\"']?([^\s\"',;]{6,})"
)
_CARD = re.compile(r"(?<![\d-])(?:\d[ -]?){13,19}(?!\d)")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,3})?\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w+])(?:\+\d{1,3}[\s.-]?\(?\d\)?|0\d)(?:[\s.-]?\d{2}){4}(?!\d)")


def mask_value(kind: str, value: str) -> str:
    """Masquage partiel : on garde juste assez pour reconnaître le type, jamais le secret."""
    if kind in {"canary", "api_key"}:
        return value[:3] + "****"
    if kind == "credit_card":
        digits = re.sub(r"\D", "", value)
        return "**** **** **** " + digits[-4:]
    if kind == "iban":
        return re.sub(r"\s+", "", value)[:4] + "****"
    if kind == "email":
        local, _, domain = value.partition("@")
        return (local[:1] + "***@" + domain) if local else "***@" + domain
    if kind == "phone":
        return "*** ** ** " + re.sub(r"\D", "", value)[-2:]
    if kind == "person":
        return "[PERSONNE]"
    return "****"


def _fold_overlaps(findings: list[Finding]) -> list[Finding]:
    chosen: list[Finding] = []
    for f in sorted(findings, key=lambda f: (PRIORITY[f.kind], f.start)):
        if all(f.end <= c.start or f.start >= c.end for c in chosen):
            chosen.append(f)
    return sorted(chosen, key=lambda f: f.start)


class PresidioDetector:
    """Détection de noms de personnes via Presidio (dépendance optionnelle)."""

    def __init__(self, languages: tuple[str, ...] = ("en", "fr")) -> None:
        from presidio_analyzer import AnalyzerEngine  # import paresseux

        self._engine = AnalyzerEngine()
        self._languages = languages

    def detect(self, text: str) -> list[Finding]:
        out: list[Finding] = []
        for lang in self._languages:
            try:
                results = self._engine.analyze(text=text, language=lang, entities=["PERSON"])
            except Exception:  # noqa: BLE001 - langue non supportée par le moteur chargé
                continue
            out += [Finding("person", r.start, r.end) for r in results if r.score >= 0.6]
        return out


def try_load_presidio() -> PersonDetector | None:
    try:
        return PresidioDetector()
    except Exception:  # noqa: BLE001 - Presidio ou son modèle NLP absent : mode regex seule
        return None


# ----------------------------------------------------------------------------- guard
class OutputGuard(Guard):
    module = "D"

    def __init__(
        self,
        canary_tokens: tuple[str, ...] | list[str] = DEFAULT_CANARIES,
        person_detector: PersonDetector | None = None,
        *,
        mask_pii: bool = True,
    ) -> None:
        self.canary_tokens = tuple(t for t in canary_tokens if t)
        self.person_detector = person_detector
        self.mask_pii = mask_pii

    @classmethod
    def from_policy(cls, policy_path: str | Path, person_detector: PersonDetector | None = None) -> OutputGuard:
        import yaml

        data = yaml.safe_load(Path(policy_path).read_text(encoding="utf-8")) or {}
        canaries = (data.get("output") or {}).get("canary_tokens") or DEFAULT_CANARIES
        return cls(tuple(canaries), person_detector)

    @property
    def degraded(self) -> bool:
        """Dégradé = pas de détection de noms (Presidio absent) ; e-mails et téléphones restent détectés."""
        return self.person_detector is None

    # -- détection ---------------------------------------------------------------------
    def find(self, text: str) -> list[Finding]:
        found: list[Finding] = []
        for token in self.canary_tokens:
            for m in re.finditer(re.escape(token), text):
                found.append(Finding("canary", m.start(), m.end()))
        for pattern in _API_KEY_PATTERNS:
            found += [Finding("api_key", m.start(), m.end()) for m in pattern.finditer(text)]
        for m in _KEY_VALUE.finditer(text):
            found.append(Finding("api_key", m.start(1), m.end(1)))
        for m in _CARD.finditer(text):
            if luhn_valid(re.sub(r"\D", "", m.group(0))):
                found.append(Finding("credit_card", m.start(), m.end()))
        for m in _IBAN.finditer(text):
            if iban_valid(m.group(0)):
                found.append(Finding("iban", m.start(), m.end()))
        if self.mask_pii:
            found += [Finding("email", m.start(), m.end()) for m in _EMAIL.finditer(text)]
            found += [Finding("phone", m.start(), m.end()) for m in _PHONE.finditer(text)]
            if self.person_detector is not None:
                found += self.person_detector.detect(text)
        return _fold_overlaps(found)

    @staticmethod
    def mask(text: str, findings: list[Finding]) -> str:
        out, cursor = [], 0
        for f in findings:
            out.append(text[cursor : f.start])
            out.append(mask_value(f.kind, text[f.start : f.end]))
            cursor = f.end
        out.append(text[cursor:])
        return "".join(out)

    # -- API Guard ---------------------------------------------------------------------
    @staticmethod
    def _extract_text(context: dict[str, Any]) -> str:
        if context.get("text") is not None:
            return str(context["text"])
        args = context.get("arguments")
        if args is not None:
            return args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
        return ""

    def check(self, context: dict[str, Any]) -> Verdict:
        started = time.perf_counter()
        text = self._extract_text(context)
        channel = str(context.get("channel") or "final_response")  # final_response | tool_arguments
        correlation_id = context.get("correlation_id") or context.get("correlationId")

        findings = self.find(text)
        kinds = sorted({f.kind for f in findings})
        score = max((SCORES[f.kind] for f in findings), default=0.0)
        canary = any(f.kind == "canary" for f in findings)

        if findings:
            counts = {k: sum(1 for f in findings if f.kind == k) for k in kinds}
            reason = "données sensibles détectées : " + ", ".join(f"{k} ×{n}" for k, n in counts.items())
            if canary:
                reason += " (canary token : fuite avérée)"
        else:
            reason = "aucune donnée sensible détectée"
        if self.degraded:
            reason += " ; mode dégradé : pas de détection de noms (Presidio absent)"

        return Verdict(
            module=self.module,
            score=score,
            attack_type=(AttackType.DATA_LEAK if findings else AttackType.NONE).value,
            reason=reason,
            cleaned=self.mask(text, findings) if findings else text,
            risk_level=risk_from_score(score).value,
            correlation_id=correlation_id,
            degraded=self.degraded,
            latency_ms=(time.perf_counter() - started) * 1000,
            metadata={
                "canary": canary,
                "channel": channel,
                "kinds": kinds,
                # positions seulement : jamais la valeur brute
                "findings": [{"kind": f.kind, "start": f.start, "end": f.end} for f in findings],
            },
        )
