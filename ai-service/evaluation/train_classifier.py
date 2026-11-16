"""Entraîne le classifieur TF-IDF du Guard A sur le split *train* uniquement (AS-S1-015).

Le jeu de validation et le jeu de test ne sont jamais lus ici. L'artefact est écrit dans
``ai-service/models_cache/`` (ignoré par Git) : il se régénère en une commande.
"""
from __future__ import annotations

import argparse

from app.guards.classifier import DEFAULT_MODEL_PATH, TfidfClassifier

from .dataio import load_split
from .make_splits import DEFAULT_SEED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)
    train = load_split("train")
    model = TfidfClassifier.train([e.text for e in train], [e.label for e in train], seed=args.seed)
    path = model.save(DEFAULT_MODEL_PATH)
    print(f"Classifieur entraîné sur {len(train)} exemples (train uniquement) -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
