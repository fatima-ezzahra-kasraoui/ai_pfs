"""Runner de non-régression des guards (AS-S2-019).

Rejoue tous les jeux **train + validation** (jamais le test) avec les guards en mode règles
seules (déterministe, sans modèle à télécharger) et compare au résultat de référence
``evaluation/regression_baseline.json`` : le runner échoue si un cas auparavant bien classé est
maintenant mal classé. Les cas nouvellement corrigés sont signalés, sans échec.

  python -m evaluation.run_regression            # compare (utilisé en CI)
  python -m evaluation.run_regression --update   # réécrit la référence (décision explicite, à relire en PR)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.guards.content_guard import ContentGuard
from app.guards.input_guard import InputGuard
from app.guards.output_guard import OutputGuard

from .dataio import load_split
from .guard_eval import load_thresholds
from .make_splits import DEFAULT_SEED
from .synthetic import build_guard_b_cases, build_guard_d_cases

BASELINE_PATH = Path(__file__).resolve().parent / "regression_baseline.json"
REGRESSION_SPLITS = ("train", "validation")  # le test n'est jamais lu ici


def current_outcomes() -> dict[str, dict]:
    """Retourne {clé: {label, score, correct}} pour tous les cas rejoués."""
    review = load_thresholds()["injection_review"]
    a, b, d = InputGuard(), ContentGuard(), OutputGuard()
    out: dict[str, dict] = {}

    def record(key: str, label: int, score: float) -> None:
        out[key] = {"label": label, "score": round(score, 4), "correct": (score >= review) == bool(label)}

    for split in REGRESSION_SPLITS:
        examples = load_split(split)
        for ex in examples:
            record(f"A:{ex.id}", ex.label, a.check({"text": ex.text}).score)
        for case in build_guard_b_cases(examples, DEFAULT_SEED):
            record(f"B:{split}:{case['id']}", case["label"], b.check({"text": case["text"]}).score)
    for seed in (1001,):
        for case in build_guard_d_cases(seed):
            record(f"D:{case['id']}", case["label"], d.check({"text": case["text"]}).score)
    return out


def compare(baseline: dict[str, dict], current: dict[str, dict]) -> tuple[list[str], list[str], list[str]]:
    regressions = [k for k, v in baseline.items() if v["correct"] and (k not in current or not current[k]["correct"])]
    fixed = [k for k, v in current.items() if v["correct"] and k in baseline and not baseline[k]["correct"]]
    new = [k for k in current if k not in baseline]
    return sorted(regressions), sorted(fixed), sorted(new)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    args = ap.parse_args(argv)

    current = current_outcomes()
    if args.update or not args.baseline.exists():
        args.baseline.write_text(json.dumps({"reviewThreshold": load_thresholds()["injection_review"], "cases": current}, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        ok = sum(v["correct"] for v in current.values())
        print(f"Référence écrite : {ok}/{len(current)} cas bien classés -> {args.baseline.name}")
        return 0
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))["cases"]
    regressions, fixed, new = compare(baseline, current)
    ok = sum(v["correct"] for v in current.values())
    print(f"{ok}/{len(current)} cas bien classés ; corrigés : {len(fixed)} ; nouveaux : {len(new)} ; régressions : {len(regressions)}")
    for k in regressions:
        print(f"  RÉGRESSION {k} (score {current[k]['score'] if k in current else 'absent'})")
    if new:
        print("  Cas nouveaux non présents dans la référence : relancer avec --update après relecture.")
    return 1 if regressions else 0


if __name__ == "__main__":
    raise SystemExit(main())
