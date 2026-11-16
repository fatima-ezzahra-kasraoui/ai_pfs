"""Réglage des seuils sur la **validation uniquement** (AS-S4-001).

Fait varier ``injection_review`` et ``injection_block`` sur les scores des guards A et B
(cas de validation), trace précision / rappel / FPR (CSV + courbe SVG) et propose des valeurs.
Le split de test n'est jamais lu par ce script.

Règle de choix (documentée, à discuter en équipe) :
* ``injection_review`` : parmi les seuils dont le FPR sur la validation ≤ ``--max-fpr`` (5 % par défaut),
  maximiser le rappel puis le F1 ; sur un plateau de seuils équivalents, garder celui **le plus proche de la
  valeur de départ** (la validation est petite : on ne s'écarte pas du point de départ sans preuve) ;
* ``injection_block`` : parmi les seuils ≥ ``BLOCK_FLOOR`` (0,80) et ≥ review + 0,05 dont la précision sur la
  validation ≥ 0,99, garder le plus proche de la valeur de départ. Un BLOCK exige une forte conviction ; avec
  si peu de cas, une précision de 1,00 à bas seuil ne le justifie pas. À défaut, valeur actuelle conservée ;
* ``coherence_min`` : **non réglé ici** (dépend du Guard C d'É2) ; valeur de départ conservée.

``--freeze`` écrit ``config/thresholds.frozen.json`` et reporte les valeurs dans ``policy.yaml``.
Le tag Git ``thresholds-frozen`` se pose ensuite à la main (voir la sortie du script).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from app.guards.classifier import load_classifier
from app.guards.content_guard import ContentGuard
from app.guards.input_guard import InputGuard

from . import metrics as m
from .dataio import load_split
from .guard_eval import POLICY_PATH, load_thresholds, score_content_guard, score_input_guard
from .make_splits import DEFAULT_SEED
from .results import FROZEN_PATH, RESULTS_DIR, make_result, write_result
from .synthetic import build_guard_b_cases

GRID = [round(0.05 * i, 2) for i in range(1, 20)]  # 0,05 … 0,95
BLOCK_FLOOR = 0.80
DOCS_DIR = Path(__file__).resolve().parents[2] / "docs" / "tuning"


def collect_scores(use_classifier: bool) -> tuple[list[int], list[float], str | None]:
    classifier = load_classifier() if use_classifier else None
    examples = load_split("validation")
    a = score_input_guard(InputGuard(classifier), examples)
    b = score_content_guard(ContentGuard(classifier), build_guard_b_cases(examples, DEFAULT_SEED))
    rows = a + b
    return [r["label"] for r in rows], [r["score"] for r in rows], getattr(classifier, "name", None)


def choose(y: list[int], s: list[float], th: dict[str, float], max_fpr: float = 0.05) -> tuple[dict[str, float], list[str]]:
    sweep = m.threshold_sweep(y, s, GRID)
    why: list[str] = []
    ok = [r for r in sweep if r["fpr"] is not None and r["fpr"] <= max_fpr and r["recall"]]  # rappel > 0 : un seuil qui ne détecte rien n'est pas un choix
    if not ok:
        why.append(f"Aucun seuil ne respecte FPR ≤ {max_fpr:.0%} : valeur de départ conservée.")
        return dict(th), why
    best = max((r["recall"], r["f1"] or 0.0) for r in ok)
    plateau = [r["threshold"] for r in ok if (r["recall"], r["f1"] or 0.0) == best]
    review = min(plateau, key=lambda t: (abs(t - th["injection_review"]), t))
    n_pos = sum(y)
    why.append(f"Validation : {len(y)} cas dont {n_pos} attaques (échantillon petit : les seuils sont indicatifs).")
    why.append(f"injection_review = {review} : plateau {plateau[0]}–{plateau[-1]} (rappel {best[0]:.3f}, FPR ≤ {max_fpr:.0%}), valeur la plus proche du point de départ {th['injection_review']}.")
    block = th["injection_block"]
    cands = [r["threshold"] for r in sweep if r["threshold"] >= max(review + 0.05, BLOCK_FLOOR) and r["precision"] is not None and r["precision"] >= 0.99]
    if cands:
        block = min(cands, key=lambda t: (abs(t - th["injection_block"]), t))
        why.append(f"injection_block = {block} : seuil ≥ {BLOCK_FLOOR} et ≥ review + 0,05, précision ≥ 0,99 sur la validation, le plus proche du point de départ {th['injection_block']}.")
    else:
        why.append("Aucun seuil de blocage n'atteint une précision ≥ 0,99 : injection_block conservé.")
    why.append("coherence_min non réglé : dépend du Guard C (É2).")
    return {"injection_review": review, "injection_block": block, "coherence_min": th["coherence_min"]}, why


def svg_curves(sweep: list[dict], chosen: dict[str, float]) -> str:
    w, h, pad = 560, 340, 44
    def x(t): return pad + (w - 2 * pad) * (t - 0.05) / 0.9
    def y(v): return h - pad - (h - 2 * pad) * v
    series = {"Précision": ("precision", "#2563eb", ""), "Rappel": ("recall", "#16a34a", ""), "FPR": ("fpr", "#dc2626", "5 4")}
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="sans-serif" font-size="11">', f'<rect width="{w}" height="{h}" fill="white"/>']
    for v in (0, 0.25, 0.5, 0.75, 1):
        parts.append(f'<line x1="{pad}" x2="{w - pad}" y1="{y(v)}" y2="{y(v)}" stroke="#e5e7eb"/><text x="{pad - 6}" y="{y(v) + 4}" text-anchor="end">{v:.2f}</text>')
    for t in (0.1, 0.3, 0.5, 0.7, 0.9):
        parts.append(f'<text x="{x(t)}" y="{h - pad + 16}" text-anchor="middle">{t}</text>')
    for key, color, dash in series.values():
        pts = " ".join(f"{x(r['threshold']):.1f},{y(r[key]):.1f}" for r in sweep if r[key] is not None)
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="{dash}" points="{pts}"/>')
    for name, color in (("injection_review", "#6b7280"), ("injection_block", "#111827")):
        parts.append(f'<line x1="{x(chosen[name])}" x2="{x(chosen[name])}" y1="{pad}" y2="{h - pad}" stroke="{color}" stroke-dasharray="2 3"/><text x="{x(chosen[name]) + 3}" y="{pad + 10}" fill="{color}">{name.split("_")[1]}</text>')
    for i, (label, (_, color, _d)) in enumerate(series.items()):
        parts.append(f'<rect x="{pad + 90 * i}" y="8" width="10" height="10" fill="{color}"/><text x="{pad + 90 * i + 14}" y="17">{label}</text>')
    parts.append(f'<text x="{w / 2}" y="{h - 6}" text-anchor="middle">seuil de score (validation uniquement)</text></svg>')
    return "\n".join(parts)


def update_policy(path: Path, chosen: dict[str, float]) -> None:
    text = path.read_text(encoding="utf-8")
    for key, val in chosen.items():
        text = re.sub(rf"(^\s*{key}:\s*)[0-9.]+", rf"\g<1>{val}", text, flags=re.M)
    text = text.replace("thresholds:                  # TEMPORARY", "thresholds:                  # GELÉS (thresholds.frozen.json)")
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-fpr", type=float, default=0.05)
    ap.add_argument("--no-classifier", action="store_true")
    ap.add_argument("--freeze", action="store_true", help="gèle les seuils choisis (écrit thresholds.frozen.json et policy.yaml)")
    args = ap.parse_args(argv)

    th = load_thresholds()
    y, s, clf = collect_scores(not args.no_classifier)
    sweep = m.threshold_sweep(y, s, GRID)
    chosen, why = choose(y, s, th, args.max_fpr)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    with (DOCS_DIR / "threshold_sweep_validation.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["threshold", "precision", "recall", "f1", "fpr", "tp", "fp", "tn", "fn"])
        for r in sweep:
            w.writerow([r["threshold"], *(("" if r[k] is None else round(r[k], 4)) for k in ("precision", "recall", "f1", "fpr")), *r["confusion"].values()])
    (DOCS_DIR / "threshold_curves_validation.svg").write_text(svg_curves(sweep, chosen), encoding="utf-8")

    result = make_result(
        kind="threshold_tuning", name="threshold_tuning", split="validation", status="preliminary", seed=DEFAULT_SEED,
        config={"grid": GRID, "maxFpr": args.max_fpr, "classifier": clf, "casesUsed": "guards A et B, split validation"},
        metrics={"before": th, "chosen": chosen, "sweep": sweep, "rationale": why, "frozen": False},
        notes=["Le split de test n'a pas été lu. Réglage sur la validation uniquement."],
    )
    path = write_result(result, RESULTS_DIR)
    print("Seuils proposés :", chosen)
    for line in why:
        print(" -", line)
    print("Résultat :", path.name)

    if args.freeze:
        FROZEN_PATH.write_text(json.dumps({"thresholds": chosen, "frozenFrom": path.name, "tag": "thresholds-frozen"}, indent=2) + "\n", encoding="utf-8")
        update_policy(POLICY_PATH, chosen)
        print("Seuils gelés. Poser le tag : git tag thresholds-frozen && git push origin thresholds-frozen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
