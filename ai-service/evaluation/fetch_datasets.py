"""Récupération de deepset/prompt-injections (AS-S1-011).

Écrit ``evaluation/data/raw/deepset_prompt_injections.jsonl`` (texte + label). Le dossier
``raw/`` est ignoré par Git : le jeu est re-téléchargeable, jamais committé.

Prérequis : ``pip install datasets`` (voir requirements-ml.txt) et un accès à huggingface.co.
Vérifier la licence sur la carte du jeu avant citation dans le rapport, puis la reporter
dans ``evaluation/data/README.md``.
"""
from __future__ import annotations

import json
import sys

from .dataio import RAW_DIR

DATASET = "deepset/prompt-injections"


def main() -> int:
    try:
        from datasets import load_dataset
    except ImportError:
        print("Le paquet `datasets` est requis : pip install -r requirements-ml.txt")
        return 2
    try:
        ds = load_dataset(DATASET)
    except Exception as exc:  # noqa: BLE001 - réseau, quota, dataset retiré
        print(f"Téléchargement impossible ({exc}). Les splits restent construits à partir des exemples français seuls.")
        return 1
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / "deepset_prompt_injections.jsonl"
    n = 0
    with out.open("w", encoding="utf-8") as fh:
        for split in ds.values():
            for row in split:
                fh.write(json.dumps({"text": row["text"], "label": int(row["label"])}, ensure_ascii=False) + "\n")
                n += 1
    print(f"{n} exemples écrits dans {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
