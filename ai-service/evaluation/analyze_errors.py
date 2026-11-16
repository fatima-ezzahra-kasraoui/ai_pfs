"""Liste les faux positifs / faux négatifs des guards A, B et D sur la validation (AS-S3-021).

Lit les derniers fichiers ``guard_{a,b,d}_validation_*.json`` et écrit ``docs/analyse-erreurs-validation.md``.
La liste est générée ; l'analyse qualitative est écrite à la main dans la section « Analyse » du document
(non écrasée : le script ne réécrit que la partie générée entre les marqueurs).
"""
from __future__ import annotations

from pathlib import Path

from .dataio import load_split
from .make_splits import DEFAULT_SEED
from .results import load_results
from .synthetic import build_guard_b_cases, build_guard_d_cases

DOC = Path(__file__).resolve().parents[2] / "docs" / "analyse-erreurs-validation.md"
BEGIN, END = "<!-- BEGIN GENERATED -->", "<!-- END GENERATED -->"


def generated() -> str:
    results = [r for r in load_results() if r["kind"] == "detection" and r["split"] == "validation" and r["name"] in {"guard_a", "guard_b", "guard_d"}]
    val = load_split("validation")
    texts = {f"{e.id}": e.text for e in val}
    texts.update({c["id"]: c["text"] for c in build_guard_b_cases(val, DEFAULT_SEED)})
    texts.update({c["id"]: c["text"] for c in build_guard_d_cases(1001)})
    out = []
    for name in ("guard_a", "guard_b", "guard_d"):
        sel = [r for r in results if r["name"] == name]
        if not sel:
            out += [f"### {name}", "Aucun résultat de validation.", ""]
            continue
        r = max(sel, key=lambda x: x["generatedAt"])
        m = r["metrics"]
        out += [f"### {name} — `{r['_file']}`", f"n = {m['n']} ; confusion = {m['confusion']} ; seuil = {m['threshold']}", ""]
        for title, key in (("Faux négatifs", "falseNegatives"), ("Faux positifs", "falsePositives")):
            items = m["errors"][key]
            out.append(f"**{title} ({len(items)})**")
            out += [f"- `{i['id']}` (score {i['score']}) — {texts.get(i['id'], '?')[:140]!r}" for i in items] or ["- aucun"]
            out.append("")
    return "\n".join(out)


def main() -> int:
    body = f"{BEGIN}\n{generated()}\n{END}"
    if DOC.exists() and BEGIN in DOC.read_text(encoding="utf-8"):
        text = DOC.read_text(encoding="utf-8")
        head, rest = text.split(BEGIN, 1)
        tail = rest.split(END, 1)[1]
        DOC.write_text(head + body + tail, encoding="utf-8")
    else:
        DOC.parent.mkdir(parents=True, exist_ok=True)
        DOC.write_text("# Analyse des erreurs de détection sur la validation (AS-S3-021)\n\n## Erreurs restantes (générées)\n\n" + body + "\n\n## Analyse\n\n*À compléter par l'équipe (voir ci-dessous).*\n", encoding="utf-8")
    print("écrit :", DOC)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
