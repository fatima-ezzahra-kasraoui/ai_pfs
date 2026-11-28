"""Compare plusieurs classifieurs du Guard A, calibre leur seuil et retient le plus précis.

Protocole (le split *test* n'est JAMAIS lu) :
1. entraînement sur ``train`` + ``extra_train`` ;
2. seuil de revue par modèle : validation croisée (5 plis) sur l'entraînement -> probabilités hors-pli ->
   plus petit seuil qui garde FPR <= ``--max-fpr`` (défaut 2 %) ;
3. mesure sur ``validation`` + ``extra_eval`` (données jamais vues) avec le seuil calibré, en
   configuration de production (règles + classifieur) : Précision, Rappel, F1, FPR ;
4. sélection : meilleur rappel parmi ceux dont le FPR <= max-fpr, puis meilleur F1 ;
5. le gagnant est ré-entraîné et sauvegardé (``models_cache/guard_a_best.joblib``) ; ``load_classifier()`` le charge.

``--hf-model NOM`` ajoute un modèle Hugging Face pré-entraîné (mesuré sans ré-entraînement, seuil calibré sur
l'entraînement faute de plis) ; un modèle indisponible est « non mesuré », jamais estimé.

Utilisation : ``python -m evaluation.select_best_model [--hf-model NOM ...] [--max-fpr 0.02]``
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from app.guards.classifier import BEST_MODEL_PATH, HFClassifier
from app.guards.input_guard import InputGuard

from .dataio import load_extra, load_split
from .guard_eval import load_thresholds, misclassified, score_input_guard, summarize
from .make_splits import DEFAULT_SEED
from .model_zoo import SKLEARN_CANDIDATES, train_sklearn
from .results import RESULTS_DIR


def calibrate_threshold(scores: list[float], labels: list[int], max_fpr: float, floor: float = 0.30) -> float:
    """Plus petit seuil (>= ``floor``) dont le FPR <= ``max_fpr`` ; maximise donc le rappel à FPR borné."""
    neg = sorted(s for s, y in zip(scores, labels) if y == 0)
    cands = sorted({round(s, 4) for s in scores} | {0.5})
    for t in cands:
        if t < floor:
            continue
        fpr = sum(s >= t for s in neg) / max(1, len(neg))
        if fpr <= max_fpr:
            return float(t)
    return 0.90


def oof_scores(name: str, texts: list[str], labels: list[int], seed: int) -> list[float]:
    from sklearn.model_selection import StratifiedKFold

    out = [0.0] * len(texts)
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=seed).split(texts, labels):
        m = train_sklearn(name, [texts[i] for i in tr], [labels[i] for i in tr], seed)
        for i, p in zip(te, m.predict_proba([texts[i] for i in te])):
            out[i] = p
    return out


def run(hf_models: list[str], max_fpr: float, seed: int) -> dict:
    train = load_split("train") + load_extra("extra_train")
    held = load_split("validation") + load_extra("extra_eval")
    texts, labels = [e.text for e in train], [e.label for e in train]
    rows: dict[str, dict] = {}
    trained: dict[str, object] = {}

    def evaluate(name: str, clf, thr: float) -> dict:
        guard = InputGuard(clf)
        scored = score_input_guard(guard, held)
        res = summarize(scored, thr)
        res["measured"] = True
        res["threshold"] = thr
        res["errors"] = {k: [r["id"] for r in v] for k, v in misclassified(scored, thr).items()}
        return res

    for name in SKLEARN_CANDIDATES:
        oof = oof_scores(name, texts, labels, seed)
        thr = calibrate_threshold(oof, labels, max_fpr)
        clf = train_sklearn(name, texts, labels, seed)
        trained[name] = clf
        rows[name] = evaluate(name, clf, thr)
    for model in hf_models:
        key = f"hf:{model}"
        try:
            clf = HFClassifier(model)
            thr = calibrate_threshold(clf.predict_proba(texts), labels, max_fpr)
            rows[key] = evaluate(key, clf, thr)
        except Exception as exc:  # noqa: BLE001 - dépendance absente, réseau, modèle introuvable
            rows[key] = {"measured": False, "reason": f"{type(exc).__name__}: {str(exc)[:160]}"}
    return {"rows": rows, "trained": trained, "nTrain": len(train), "nHeldOut": len(held)}


def pick(rows: dict, max_fpr: float) -> str | None:
    ok = {n: r for n, r in rows.items() if r["measured"] and r["fpr"] is not None and r["fpr"] <= max_fpr and r["recall"] is not None}
    return max(ok, key=lambda n: (ok[n]["recall"], ok[n]["f1"] or 0.0)) if ok else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hf-model", action="append", default=[])
    ap.add_argument("--max-fpr", type=float, default=0.02)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)

    out = run(args.hf_model, args.max_fpr, args.seed)
    rows = out["rows"]
    print(f"entraînement : {out['nTrain']} ex. ; mesure sur données jamais vues : {out['nHeldOut']} ex. ; FPR max toléré : {args.max_fpr:.0%}\n")
    print(f"{'modèle':<24}{'seuil':>7}{'Préc.':>8}{'Rappel':>8}{'F1':>8}{'FPR':>8}{'p50 ms':>9}")
    for n, r in rows.items():
        if not r["measured"]:
            print(f"{n:<24} non mesuré : {r['reason']}")
            continue
        print(f"{n:<24}{r['threshold']:>7.2f}{r['precision']:>8.3f}{r['recall']:>8.3f}{r['f1']:>8.3f}{r['fpr']:>8.3f}{r['latencyMs']['p50']:>9.2f}")
    best = pick(rows, args.max_fpr)
    print("\nMeilleur modèle :", best or "aucun (FPR trop élevé partout)")
    if best:
        print(f"Seuil de revue recommandé pour {best} : {rows[best]['threshold']:.2f} (policy.yaml: injection_review, actuellement {load_thresholds()['injection_review']})")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS_DIR / f"model_selection_{stamp}.json"
    path.write_text(json.dumps({"best": best, "maxFpr": args.max_fpr, "seed": args.seed, "nTrain": out["nTrain"], "nHeldOut": out["nHeldOut"], "candidates": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    print("résultats :", path)
    if best and not args.no_save and best in out["trained"]:
        saved = out["trained"][best].save(BEST_MODEL_PATH)
        print("modèle sauvegardé :", saved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
