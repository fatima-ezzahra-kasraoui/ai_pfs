"""Mesure du Guard B sur InjecAgent (jeu externe, MIT) — AS-S1-014 / AS-S3-022.

InjecAgent fournit, pour chaque cas, la réponse d'outil *contenant* l'instruction de l'attaquant
(« Tool Response ») et un gabarit (« Tool Response Template ») avec un emplacement
``<Attacker Instruction>``. On en tire :

* positif : la réponse d'outil avec l'injection ;
* négatif : le gabarit dont l'emplacement est vidé (même contenu d'outil, sans injection).

C'est une mesure de **détection** (pas d'ASR : il faudrait un LLM). Les règles n'ont jamais été réglées sur
ces données : elles sont en anglais alors que nos règles et exemples sont surtout français, donc le résultat
est une borne honnête de généralisation. Les données ne sont pas copiées dans ce dépôt : fournir le chemin
d'un clone (`git clone https://github.com/uiuc-kang-lab/InjecAgent`).

  python -m evaluation.injecagent_guard_b --repo /chemin/InjecAgent [--sample 300] [--no-classifier]
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from app.guards.classifier import load_classifier
from app.guards.content_guard import ContentGuard

from .guard_eval import load_thresholds, summarize
from .make_splits import DEFAULT_SEED
from .results import make_result, write_result

FILES = ("test_cases_dh_base.json", "test_cases_ds_base.json")
PLACEHOLDER = "<Attacker Instruction>"


def build_cases(repo: Path, sample: int, seed: int) -> list[dict]:
    rows = []
    for name in FILES:
        for i, case in enumerate(json.loads((repo / "data" / name).read_text(encoding="utf-8"))):
            template = case.get("Tool Response Template", "")
            positive = case.get("Tool Response", "")
            if PLACEHOLDER not in template or not positive:
                continue
            rows.append({"id": f"{name[11:13]}-{i:04d}", "attack": positive, "benign": template.replace(PLACEHOLDER, "").strip(), "type": case.get("Attack Type")})
    rng = random.Random(seed)
    rng.shuffle(rows)
    cases = []
    for r in rows[:sample]:
        cases.append({"id": f"{r['id']}-inj", "text": r["attack"], "label": 1, "type": r["type"]})
        cases.append({"id": f"{r['id']}-ben", "text": r["benign"], "label": 0, "type": r["type"]})
    return cases


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--sample", type=int, default=300, help="nombre de paires (injection, bénin)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--no-classifier", action="store_true")
    args = ap.parse_args(argv)

    clf = None if args.no_classifier else load_classifier()
    guard = ContentGuard(clf)
    cases = build_cases(args.repo, args.sample, args.seed)
    review = load_thresholds()["injection_review"]
    scored = []
    for c in cases:
        v = guard.check({"text": c["text"]})
        scored.append({"id": c["id"], "label": c["label"], "score": round(v.score, 6), "latencyMs": round(v.latency_ms or 0, 4), "type": c["type"]})
    metrics = summarize(scored, review)
    fn = [r for r in scored if r["label"] == 1 and r["score"] < review]
    metrics["falseNegativeByType"] = {t: sum(1 for r in fn if r["type"] == t) for t in sorted({r["type"] for r in fn})}
    metrics["falseNegatives"] = [r["id"] for r in fn]
    metrics["falsePositives"] = [r["id"] for r in scored if r["label"] == 0 and r["score"] >= review]
    head = (args.repo / ".git" / "HEAD").read_text().strip() if (args.repo / ".git" / "HEAD").exists() else "unknown"
    result = make_result(
        kind="detection", name="guard_b_injecagent", split="validation", status="preliminary", seed=args.seed,
        config={"external": True, "dataset": "InjecAgent (MIT)", "datasetRef": head, "pairs": len(cases) // 2, "classifier": getattr(clf, "name", None), "threshold": review, "tunedOnThisData": False},
        metrics=metrics, notes=["Jeu externe jamais utilisé pour régler les règles ; mesure de détection (pas d'ASR). Texte anglais : les règles sont surtout françaises."],
    )
    path = write_result(result)
    print(f"Guard B sur InjecAgent : n={metrics['n']} P={metrics['precision']} R={metrics['recall']} F1={metrics['f1']} FPR={metrics['fpr']} -> {path.name}")
    print("Faux négatifs par type :", metrics["falseNegativeByType"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
