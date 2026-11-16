"""Construction reproductible des splits entraînement / validation / test (AS-S1-011).

Sources :
* ``french_lot*.json``                    exemples français rédigés par l'équipe ;
* ``raw/deepset_prompt_injections.jsonl`` optionnel, produit par ``fetch_datasets.py``.

Garanties : graine fixe, dédoublonnage *avant* découpage (aucun texte identique ne peut
se retrouver dans deux splits), découpage stratifié par (source, label), manifeste avec
empreintes SHA-256. Le split *test* ne sert qu'à la mesure finale (jamais au réglage).

Utilisation : ``python -m evaluation.make_splits [--seed 42]``
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from app.core.text import fold, normalize

from .dataio import DATA_DIR, RAW_DIR, SPLITS

RATIOS = {"train": 0.70, "validation": 0.15, "test": 0.15}
DEFAULT_SEED = 42


def _key(text: str) -> str:
    return fold(normalize(text)[0])


def load_french(data_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(data_dir.glob("french_lot*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        lot = data["lot"]
        for label, field in ((1, "injection"), (0, "normal")):
            for i, text in enumerate(data[field]):
                rows.append({"id": f"fr-l{lot}-{'inj' if label else 'nor'}-{i:03d}", "text": text, "label": label, "source": f"french_lot{lot}", "lang": "fr", "group": "fr"})
    return rows


def load_deepset(raw_dir: Path) -> list[dict]:
    path = raw_dir / "deepset_prompt_injections.jsonl"
    if not path.exists():
        return []
    rows: list[dict] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            d = json.loads(line)
            rows.append({"id": f"deepset-{i:04d}", "text": d["text"], "label": int(d["label"]), "source": "deepset/prompt-injections", "lang": d.get("lang", "mixed"), "group": "deepset"})
    return rows


def dedupe(rows: list[dict]) -> tuple[list[dict], int]:
    seen: dict[str, dict] = {}
    dropped = 0
    for row in rows:
        k = _key(row["text"])
        if not k:
            dropped += 1
            continue
        if k in seen:
            dropped += 1
            continue
        seen[k] = row
    return list(seen.values()), dropped


def split_counts(n: int) -> tuple[int, int, int]:
    """Tailles (train, validation, test) ; au moins un exemple par split si n >= 3."""
    if n < 3:
        return n, 0, 0
    n_val = max(1, round(n * RATIOS["validation"]))
    n_test = max(1, round(n * RATIOS["test"]))
    return n - n_val - n_test, n_val, n_test


def build_splits(rows: list[dict], seed: int = DEFAULT_SEED) -> dict[str, list[dict]]:
    rng = random.Random(seed)
    strata: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in sorted(rows, key=lambda r: r["id"]):
        strata[(row["group"], row["label"])].append(row)
    out: dict[str, list[dict]] = {s: [] for s in SPLITS}
    for stratum in sorted(strata):
        items = strata[stratum][:]
        rng.shuffle(items)
        n_train, n_val, _ = split_counts(len(items))
        out["train"] += items[:n_train]
        out["validation"] += items[n_train : n_train + n_val]
        out["test"] += items[n_train + n_val :]
    for s in SPLITS:
        out[s].sort(key=lambda r: r["id"])
    return out


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_splits(splits: dict[str, list[dict]], data_dir: Path, seed: int, dropped: int, sources: list[Path]) -> dict:
    manifest: dict = {"seed": seed, "ratios": RATIOS, "duplicatesDropped": dropped, "splits": {}, "sources": {}}
    for name, rows in splits.items():
        path = data_dir / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps({k: r[k] for k in ("id", "text", "label", "source", "lang")}, ensure_ascii=False) + "\n")
        manifest["splits"][name] = {
            "file": path.name,
            "total": len(rows),
            "injection": sum(r["label"] for r in rows),
            "normal": sum(1 - r["label"] for r in rows),
            "bySource": dict(Counter(r["source"] for r in rows)),
            "sha256": _sha256(path),
        }
    for src in sources:
        manifest["sources"][src.name] = _sha256(src)
    (data_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args(argv)

    raw_dir = RAW_DIR if args.data_dir == DATA_DIR else args.data_dir / "raw"
    rows = load_french(args.data_dir) + load_deepset(raw_dir)
    if not rows:
        print("Aucune donnée source trouvée.")
        return 1
    rows, dropped = dedupe(rows)
    splits = build_splits(rows, args.seed)
    sources = sorted(args.data_dir.glob("french_lot*.json")) + sorted(raw_dir.glob("deepset_prompt_injections.jsonl"))
    manifest = write_splits(splits, args.data_dir, args.seed, dropped, sources)
    for name, info in manifest["splits"].items():
        print(f"{name:<11} total={info['total']:>4}  injections={info['injection']:>4}  normales={info['normal']:>4}")
    print(f"doublons écartés : {dropped} ; graine : {args.seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
