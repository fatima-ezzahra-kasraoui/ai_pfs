"""Mesure des guards A, B et D (AS-S1-027, AS-S2-022).

Par défaut : split *validation*, résultats ``preliminary``. Le split *test* n'est accessible
que via ``run_benchmark`` (campagne officielle, seuils gelés).

Utilisation : ``python -m evaluation.measure_guards [--guards A B D] [--no-classifier]``
Les chiffres sont écrits dans ``evaluation/results/`` avec la date et le commit ; rien n'est
affiché qui n'ait été calculé.
"""
from __future__ import annotations

import argparse

from app.guards.classifier import load_classifier
from app.guards.content_guard import ContentGuard
from app.guards.input_guard import InputGuard
from app.guards.output_guard import OutputGuard, try_load_presidio

from .dataio import load_split
from .guard_eval import load_thresholds, misclassified, score_content_guard, score_input_guard, score_output_guard, summarize
from .make_splits import DEFAULT_SEED
from .results import make_result, write_result
from .synthetic import build_guard_b_cases, build_guard_d_cases

SPLIT = "validation"
D_SEED = {"validation": 1001, "test": 2002}


def measure(guards: list[str], use_classifier: bool, seed: int = DEFAULT_SEED) -> list[str]:
    thresholds = load_thresholds()
    review = thresholds["injection_review"]
    classifier = load_classifier() if use_classifier else None
    examples = load_split(SPLIT)
    written: list[str] = []

    for g in guards:
        if g == "A":
            guard = InputGuard(classifier)
            scored = score_input_guard(guard, examples)
            name, extra = "guard_a", {"classifier": getattr(classifier, "name", None)}
        elif g == "B":
            guard = ContentGuard(classifier)
            cases = build_guard_b_cases(examples, seed)
            scored = score_content_guard(guard, cases)
            name, extra = "guard_b", {"classifier": getattr(classifier, "name", None), "casesDerivedFrom": "split validation encapsulé (synthetic.py)"}
        elif g == "D":
            guard = OutputGuard(person_detector=try_load_presidio())
            cases = build_guard_d_cases(D_SEED[SPLIT])
            scored = score_output_guard(guard, cases)
            name, extra = "guard_d", {"presidio": guard.person_detector is not None, "casesDerivedFrom": "synthetic.py (valeurs factices)"}
        else:
            raise ValueError(f"guard inconnu : {g}")

        metrics = summarize(scored, review)
        if g == "D":
            metrics["secretsStillInClear"] = sum(1 for r in scored if r.get("secretStillInClear"))
        metrics["errors"] = misclassified(scored, review)
        notes = ["Mesure préliminaire sur la validation ; seuils TEMPORARY."]
        if g in {"A", "B"} and classifier is None:
            notes.append("Mode dégradé : règles seules (aucun classifieur chargé).")
        result = make_result(
            kind="detection", name=name, split=SPLIT, status="preliminary", seed=seed,
            config={"thresholds": thresholds, **extra}, metrics=metrics, cases=scored, notes=notes,
        )
        path = write_result(result)
        written.append(str(path))
        print(f"[{g}] n={metrics['n']} P={_fmt(metrics['precision'])} R={_fmt(metrics['recall'])} F1={_fmt(metrics['f1'])} FPR={_fmt(metrics['fpr'])} -> {path.name}")
    return written


def _fmt(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guards", nargs="+", default=["A", "B", "D"], choices=["A", "B", "D"])
    parser.add_argument("--no-classifier", action="store_true", help="règles seules (mode dégradé)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)
    measure(args.guards, not args.no_classifier, args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
