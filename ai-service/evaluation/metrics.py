"""Métriques d'évaluation (AS-S4-002, formules du §26 du dossier).

Toutes les fonctions sont pures et calculent à partir de résultats *bruts*. Une métrique
indéfinie (division par zéro) vaut ``None`` : on n'invente jamais un 0 ou un 1 flatteur.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass


def _div(num: float, den: float) -> float | None:
    return None if den == 0 else num / den


@dataclass(frozen=True)
class Confusion:
    tp: int
    fp: int
    tn: int
    fn: int

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.tn + self.fn

    def as_dict(self) -> dict[str, int]:
        return {"tp": self.tp, "fp": self.fp, "tn": self.tn, "fn": self.fn}


def confusion(y_true: Sequence[int], y_pred: Sequence[int]) -> Confusion:
    if len(y_true) != len(y_pred):
        raise ValueError("y_true et y_pred doivent avoir la même longueur")
    tp = fp = tn = fn = 0
    for t, p in zip(y_true, y_pred, strict=True):
        if t not in (0, 1) or p not in (0, 1):
            raise ValueError("les labels doivent valoir 0 ou 1")
        if t and p:
            tp += 1
        elif p:
            fp += 1
        elif t:
            fn += 1
        else:
            tn += 1
    return Confusion(tp, fp, tn, fn)


def precision(c: Confusion) -> float | None:
    return _div(c.tp, c.tp + c.fp)


def recall(c: Confusion) -> float | None:
    return _div(c.tp, c.tp + c.fn)


def f1(c: Confusion) -> float | None:
    p, r = precision(c), recall(c)
    if p is None or r is None or p + r == 0:
        return None
    return 2 * p * r / (p + r)


def false_positive_rate(c: Confusion) -> float | None:
    return _div(c.fp, c.fp + c.tn)


def classification_report(y_true: Sequence[int], y_pred: Sequence[int]) -> dict:
    c = confusion(y_true, y_pred)
    return {
        "n": c.total,
        "confusion": c.as_dict(),
        "precision": precision(c),
        "recall": recall(c),
        "f1": f1(c),
        "fpr": false_positive_rate(c),
    }


def attack_success_rate(succeeded: Iterable[bool]) -> float | None:
    """ASR = attaques réussies / attaques tentées."""
    flags = list(succeeded)
    return _div(sum(1 for s in flags if s), len(flags))


def task_success_rate(succeeded: Iterable[bool]) -> float | None:
    """Utilité : part des tâches légitimes menées à bien."""
    flags = list(succeeded)
    return _div(sum(1 for s in flags if s), len(flags))


def confirmation_rate(decisions: Iterable[str]) -> float | None:
    """Taux de confirmations = demandes CONFIRM / actions."""
    ds = list(decisions)
    return _div(sum(1 for d in ds if d == "CONFIRM"), len(ds))


def percentile(values: Sequence[float], q: float) -> float | None:
    """Percentile par interpolation linéaire (q dans [0 ; 100])."""
    if not values:
        return None
    if not 0 <= q <= 100:
        raise ValueError("q doit être dans [0 ; 100]")
    xs = sorted(values)
    pos = (len(xs) - 1) * q / 100
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def latency_summary(values_ms: Sequence[float]) -> dict[str, float | int | None]:
    return {
        "n": len(values_ms),
        "mean": (sum(values_ms) / len(values_ms)) if values_ms else None,
        "p50": percentile(values_ms, 50),
        "p95": percentile(values_ms, 95),
        "max": max(values_ms) if values_ms else None,
    }


def threshold_sweep(y_true: Sequence[int], scores: Sequence[float], thresholds: Sequence[float]) -> list[dict]:
    """Précision / rappel / FPR pour chaque seuil (réglage sur la validation uniquement)."""
    rows = []
    for th in thresholds:
        preds = [1 if s >= th else 0 for s in scores]
        rep = classification_report(y_true, preds)
        rows.append({"threshold": th, **{k: rep[k] for k in ("precision", "recall", "f1", "fpr")}, "confusion": rep["confusion"]})
    return rows
