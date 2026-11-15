"""Lecture des jeux de données et des splits (entraînement / validation / test)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
RAW_DIR = DATA_DIR / "raw"
SPLITS = ("train", "validation", "test")


@dataclass(frozen=True)
class Example:
    id: str
    text: str
    label: int  # 1 = injection, 0 = requête normale
    source: str
    lang: str
    split: str = ""


def load_split(name: str, data_dir: Path = DATA_DIR) -> list[Example]:
    if name not in SPLITS:
        raise ValueError(f"split inconnu : {name!r} (attendu : {SPLITS})")
    path = data_dir / f"{name}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"{path} introuvable : lancer `python -m evaluation.make_splits`")
    out: list[Example] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            out.append(Example(d["id"], d["text"], int(d["label"]), d["source"], d.get("lang", "fr"), name))
    return out


def load_manifest(data_dir: Path = DATA_DIR) -> dict:
    return json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
