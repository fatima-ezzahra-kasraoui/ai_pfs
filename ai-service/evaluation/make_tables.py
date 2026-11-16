"""Génère le tableau de résultats du §26 et la liste des échecs (AS-S4-008).

Une ligne par famille d'attaque et une ligne globale : ASR sans protection (E1), ASR avec règles
simples (E2), ASR avec AgentShield (E3), rappel de détection (E3), faux positifs (E3, global
seulement), latence médiane et p95 (E3). **Aucune valeur n'est saisie à la main** : tout est lu dans
``evaluation/results/`` et chaque ligne cite ses fichiers sources. Une valeur absente s'écrit « n/a ».

  python -m evaluation.make_tables --split validation --status preliminary
"""
from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path

from .results import RESULTS_DIR, load_results

OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "resultats"
FAMILIES = ("direct_injection", "indirect_injection", "data_leak", "tool_abuse")
LABELS = {"direct_injection": "Injection directe", "indirect_injection": "Injection indirecte", "data_leak": "Fuite de données", "tool_abuse": "Abus d'outil", "global": "Global"}
COLUMNS = ["Attaque", "ASR sans protection (E1)", "ASR règles (E2)", "ASR AgentShield (E3)", "Rappel E3", "Faux positifs E3", "Latence p50 E3 (ms)", "Latence p95 E3 (ms)", "n attaques", "Sources"]


def latest(results: list[dict], name: str, split: str, status: str) -> dict | None:
    sel = [r for r in results if r["name"] == name and r["split"] == split and r["status"] == status and r["kind"] == "benchmark"]
    return max(sel, key=lambda r: r["generatedAt"]) if sel else None


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f} %"


def _ms(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def build_rows(results: list[dict], split: str, status: str) -> tuple[list[list[str]], dict[str, dict | None]]:
    runs = {n: latest(results, n, split, status) for n in ("e1", "e2", "e3")}

    def fam_val(run: dict | None, fam: str, key: str) -> float | None:
        return None if run is None else run["metrics"]["perFamily"][fam][key]

    rows: list[list[str]] = []
    for fam in (*FAMILIES, "global"):
        e1, e2, e3 = runs["e1"], runs["e2"], runs["e3"]
        if fam == "global":
            asr = [None if r is None else r["metrics"]["asr"] for r in (e1, e2, e3)]
            recall = None if e3 is None else e3["metrics"]["detection"]["recall"]
            fp = "n/a" if e3 is None else f"{len(e3['metrics']['falsePositives'])} / {e3['metrics']['nNormal']}"
            lat = None if e3 is None else e3["metrics"]["latencyMs"]["total"]
            n = "n/a" if e3 is None else str(e3["metrics"]["nAttacks"])
        else:
            asr = [fam_val(r, fam, "asr") for r in (e1, e2, e3)]
            recall = fam_val(e3, fam, "recall")
            fp = "—"
            lat, n = None, ("n/a" if e3 is None else str(e3["metrics"]["perFamily"][fam]["attempted"]))
        sources = ", ".join(r["_file"] for r in (e1, e2, e3) if r is not None) or "aucun résultat"
        rows.append([LABELS[fam], _pct(asr[0]), _pct(asr[1]), _pct(asr[2]), _pct(recall), fp, _ms(lat and lat["p50"]) if fam == "global" else "—", _ms(lat and lat["p95"]) if fam == "global" else "—", n, sources])
    return rows, runs


def to_markdown(rows: list[list[str]], title: str, notes: list[str]) -> str:
    out = [f"# {title}", "", "| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    out += ["", *[f"- {n}" for n in notes], ""]
    return "\n".join(out)


def to_csv(rows: list[list[str]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLUMNS)
    w.writerows(rows)
    return buf.getvalue()


def failures_markdown(runs: dict[str, dict | None], scenarios: dict[str, dict]) -> str:
    out = ["# Échecs de détection (liste générée)", "", "Analyse qualitative à rédiger par l'équipe à partir de cette liste ; aucune interprétation n'est produite automatiquement.", ""]
    for name in ("e2", "e3"):
        run = runs[name]
        out.append(f"## Configuration {name.upper()}")
        if run is None:
            out += ["Aucun résultat.", ""]
            continue
        m = run["metrics"]
        out.append(f"Source : `{run['_file']}` — agent : `{run['config']['agent']}`")
        out += ["", f"### Attaques non détectées ({len(m['falseNegatives'])})"]
        out += [f"- `{i}` — {scenarios.get(i, {}).get('family', '?')} : {scenarios.get(i, {}).get('user_message', '?')[:110]}" for i in m["falseNegatives"]] or ["- aucune"]
        out += ["", f"### Faux positifs ({len(m['falsePositives'])})"]
        out += [f"- `{i}` — {scenarios.get(i, {}).get('user_message', '?')[:110]}" for i in m["falsePositives"]] or ["- aucun"]
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=["validation", "test"], default="validation")
    ap.add_argument("--status", choices=["preliminary", "official"])
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = ap.parse_args(argv)
    status = args.status or ("official" if args.split == "test" else "preliminary")

    from .run_benchmark import load_scenarios

    results = load_results(args.results_dir)
    rows, runs = build_rows(results, args.split, status)
    simulated = [n for n, r in runs.items() if r and r["config"].get("simulated")]
    notes = [f"Jeu : {args.split} ; statut : {status} ; chaque valeur est lue dans les fichiers cités.",
             "FPR : scénarios normaux dont la décision finale est BLOCK ou dont la tâche échoue."]
    if simulated:
        notes.insert(0, "**ATTENTION — agent simulé** (crédule, sans LLM, Guard C minimal) pour : " + ", ".join(simulated) + ". Ces chiffres ne sont pas l'ASR d'un vrai agent et ne doivent pas figurer dans le rapport comme résultats finaux.")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    title = f"Résultats {args.split} ({status})"
    (args.out_dir / f"table_{args.split}_{status}.md").write_text(to_markdown(rows, title, notes), encoding="utf-8")
    (args.out_dir / f"table_{args.split}_{status}.csv").write_text(to_csv(rows), encoding="utf-8")
    scenarios = {s["id"]: s for s in load_scenarios(args.split)}
    (args.out_dir / f"failures_{args.split}_{status}.md").write_text(failures_markdown(runs, scenarios), encoding="utf-8")
    print(to_markdown(rows, title, notes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
