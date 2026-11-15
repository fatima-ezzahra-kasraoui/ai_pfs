"""Spike : comparer les classifieurs candidats du Guard A sur la validation (AS-S1-015).

Candidats, dans les **mêmes conditions** (même validation, même seuil ``injection_review``) :
* ``rules``          règles FR/EN seules ;
* ``tfidf``          TF-IDF + régression logistique, entraîné sur *train* uniquement ;
* ``rules+tfidf``    fusion par maximum (configuration livrée) ;
* ``hf:<modèle>``    modèle Hugging Face (pré-entraîné ou ajusté) si ``--hf-model`` est donné et que
  ``transformers`` + ``torch`` sont installés et le modèle téléchargeable.

Un candidat indisponible est **signalé comme non mesuré**, jamais estimé. ``--write-adr`` génère
``docs/adr-002-classifier.md`` à partir du fichier de résultats (aucun chiffre saisi à la main).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from app.guards.classifier import HFClassifier, TfidfClassifier
from app.guards.input_guard import InputGuard

from .dataio import load_split
from .guard_eval import load_thresholds, score_input_guard, summarize
from .make_splits import DEFAULT_SEED
from .results import RESULTS_DIR, load_results, make_result, write_result

ADR_PATH = Path(__file__).resolve().parents[2] / "docs" / "adr-002-classifier.md"


def _fmt(x) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def compare(hf_models: list[str]) -> dict:
    review = load_thresholds()["injection_review"]
    train, val = load_split("train"), load_split("validation")
    tfidf = TfidfClassifier.train([e.text for e in train], [e.label for e in train], seed=DEFAULT_SEED)
    candidates: dict[str, InputGuard] = {
        "rules": InputGuard(None),
        "tfidf": InputGuard(tfidf, use_rules=False),
        "rules+tfidf": InputGuard(tfidf),
    }
    rows: dict[str, dict] = {}
    for name, guard in candidates.items():
        rows[name] = {"measured": True, **summarize(score_input_guard(guard, val), review)}
    for model in hf_models:
        key = f"hf:{model}"
        try:
            rows[key] = {"measured": True, **summarize(score_input_guard(InputGuard(HFClassifier(model), use_rules=False), val), review)}
        except Exception as exc:  # noqa: BLE001 - dépendance absente, réseau, modèle introuvable
            rows[key] = {"measured": False, "reason": f"{type(exc).__name__}: {str(exc)[:160]}"}
    return rows


MAX_FPR = 0.05


def pick(rows: dict) -> tuple[str | None, str]:
    """Règle de décision : plus fort rappel parmi les candidats dont le FPR ≤ 5 %, puis meilleur F1."""
    ok = {n: r for n, r in rows.items() if r["measured"] and r["fpr"] is not None and r["fpr"] <= MAX_FPR and r["recall"] is not None}
    if not ok:
        return None, "Aucun candidat mesuré ne respecte FPR ≤ 5 % : aucune décision ne peut être prise sur ces chiffres."
    best = max(ok, key=lambda n: (ok[n]["recall"], ok[n]["f1"] or 0.0))
    rejected = [f"`{n}` (FPR {r['fpr']:.3f})" for n, r in rows.items() if r["measured"] and n not in ok and r["fpr"] is not None]
    text = f"Retenir **`{best}`** : plus fort rappel ({ok[best]['recall']:.3f}) parmi les candidats dont le taux de faux positifs sur la validation ≤ 5 %."
    if rejected:
        text += " Écartés pour faux positifs excessifs : " + ", ".join(rejected) + "."
    return best, text


def render_adr(result: dict) -> str:
    rows = result["metrics"]["candidates"]
    _best, decision = pick(rows)
    lines = ["| Candidat | Précision | Rappel | F1 | FPR | Latence p50 (ms) | Latence p95 (ms) |", "|---|---|---|---|---|---|---|"]
    for name, r in rows.items():
        if not r["measured"]:
            lines.append(f"| `{name}` | non mesuré | non mesuré | non mesuré | non mesuré | non mesuré | non mesuré |")
            continue
        lat = r["latencyMs"]
        lines.append(f"| `{name}` | {_fmt(r['precision'])} | {_fmt(r['recall'])} | {_fmt(r['f1'])} | {_fmt(r['fpr'])} | {_fmt(lat['p50'])} | {_fmt(lat['p95'])} |")
    unmeasured = [f"`{n}` ({r['reason']})" for n, r in rows.items() if not r["measured"]]
    n_val = next(r["n"] for r in rows.values() if r["measured"])
    return f"""# ADR-002 — Classifieur du Guard A

*Document généré par `python -m evaluation.compare_classifiers --write-adr` à partir de
`evaluation/results/{result['_file']}` (commit `{result['commit'][:8]}`, graine {result['seed']}). Ne pas éditer les chiffres à la main.*

## Contexte
Le Guard A doit détecter les injections directes et jailbreaks en français et en anglais, sans faux positifs
sur les requêtes normales (F02). Le dossier prévoit un modèle BERT/DeBERTa ajusté sur `deepset/prompt-injections`,
avec un modèle pré-entraîné Hugging Face en plan B.

## Protocole
Mêmes conditions pour tous les candidats : jeu de **validation** ({n_val} messages, équilibré), seuil
`injection_review = {result['config']['threshold']}`, entraînement sur le split *train* uniquement. Le split de test n'est pas lu.

## Résultats mesurés (validation)
{chr(10).join(lines)}

{"Candidats non mesurés dans cet environnement : " + "; ".join(unmeasured) + "." if unmeasured else ""}

## Décision (provisoire, calculée sur les chiffres ci-dessus)
{decision}

Cette décision **n'est pas définitive** : les modèles DeBERTa / pré-entraîné n'ont pas pu être mesurés dans cet environnement.
Avant de figer l'ADR, exécuter `python -m evaluation.compare_classifiers --hf-model <nom> --write-adr` sur une machine
avec accès à Hugging Face et trancher sur les chiffres obtenus, dans les mêmes conditions.
Le champ `degraded` du verdict signifie « aucun classifieur ML actif » : il reste à `true` tant qu'un classifieur n'est pas retenu.

## Limites
- La validation est petite ; les écarts de quelques points ne sont pas significatifs.
- Les règles ont été améliorées en examinant les erreurs de la validation puis du train (AS-S3-021) : les chiffres
  de validation sont donc optimistes. Seule la campagne sur le test, une fois les seuils gelés, est une mesure honnête.
- Les exemples français ont été rédigés pour le projet (relecture croisée à tracer en PR) et partagent un style.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hf-model", action="append", default=[], help="modèle Hugging Face à comparer (répétable)")
    ap.add_argument("--write-adr", action="store_true")
    args = ap.parse_args(argv)
    rows = compare(args.hf_model)
    result = make_result(
        kind="detection", name="classifier_comparison", split="validation", status="preliminary", seed=DEFAULT_SEED,
        config={"threshold": load_thresholds()["injection_review"], "hfModels": args.hf_model},
        metrics={"candidates": rows}, notes=["Spike AS-S1-015 : mêmes conditions pour tous les candidats."],
    )
    path = write_result(result)
    for name, r in rows.items():
        print(f"{name:<14}", "non mesuré : " + r["reason"] if not r["measured"] else f"P={_fmt(r['precision'])} R={_fmt(r['recall'])} F1={_fmt(r['f1'])} FPR={_fmt(r['fpr'])} p50={_fmt(r['latencyMs']['p50'])} ms")
    if args.write_adr:
        stored = next(r for r in load_results(RESULTS_DIR) if r["_file"] == path.name)
        ADR_PATH.parent.mkdir(parents=True, exist_ok=True)
        ADR_PATH.write_text(render_adr(stored), encoding="utf-8")
        print("ADR écrit :", ADR_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
