"""Classifieurs d'injection interchangeables pour les guards A et B (AS-S1-015, ADR-002).

Trois implémentations derrière le même protocole ``Classifier`` :

* ``TfidfClassifier``  : TF-IDF (mots + caractères) + régression logistique
  (scikit-learn). Rapide, sans GPU, entraîné uniquement sur le split *train*.
* ``HFClassifier``     : modèle Hugging Face (DeBERTa/BERT ajusté ou pré-entraîné),
  chargé paresseusement ; nécessite ``requirements-ml.txt``.
* aucun classifieur    : le guard passe en mode dégradé (règles seules).

Aucune de ces classes ne fixe de seuil de décision : elles renvoient une
probabilité d'injection dans [0 ; 1].
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Protocol, Sequence

log = logging.getLogger("agentshield.classifier")

DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[2] / "models_cache" / "guard_a_tfidf.joblib"


BEST_MODEL_PATH = Path(os.environ.get("GUARD_A_BEST_PATH", Path(__file__).resolve().parents[2] / "models_cache" / "guard_a_best.joblib"))


class Classifier(Protocol):
    name: str

    def predict_proba(self, texts: Sequence[str]) -> list[float]:
        """Probabilité d'injection pour chaque texte."""
        ...


class TfidfClassifier:
    name = "tfidf-logreg"

    def __init__(self, pipeline) -> None:  # noqa: ANN001 (sklearn Pipeline)
        self._pipeline = pipeline

    @staticmethod
    def build_pipeline(seed: int = 42):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import FeatureUnion, Pipeline

        features = FeatureUnion(
            [
                ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True, strip_accents="unicode")),
                ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True, strip_accents="unicode")),
            ]
        )
        clf = LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced", random_state=seed)
        return Pipeline([("features", features), ("clf", clf)])

    @classmethod
    def train(cls, texts: Sequence[str], labels: Sequence[int], seed: int = 42) -> TfidfClassifier:
        pipeline = cls.build_pipeline(seed)
        pipeline.fit(list(texts), list(labels))
        return cls(pipeline)

    def predict_proba(self, texts: Sequence[str]) -> list[float]:
        if not texts:
            return []
        probs = self._pipeline.predict_proba(list(texts))
        positive = list(self._pipeline.classes_).index(1)
        return [float(p[positive]) for p in probs]

    def save(self, path: Path = DEFAULT_MODEL_PATH) -> Path:
        import joblib

        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._pipeline, path)
        return path

    @classmethod
    def load(cls, path: Path = DEFAULT_MODEL_PATH) -> TfidfClassifier:
        import joblib

        return cls(joblib.load(path))


class SklearnTextClassifier:
    """Classifieur scikit-learn quelconque (pipeline texte -> probabilité) : sert aux candidats du zoo de modèles."""

    def __init__(self, name: str, pipeline) -> None:  # noqa: ANN001
        self.name = name
        self._pipeline = pipeline

    def predict_proba(self, texts: Sequence[str]) -> list[float]:
        if not texts:
            return []
        probs = self._pipeline.predict_proba(list(texts))
        positive = list(self._pipeline.classes_).index(1)
        return [float(p[positive]) for p in probs]

    def save(self, path: Path) -> Path:
        import joblib

        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"name": self.name, "pipeline": self._pipeline}, path)
        return path

    @classmethod
    def load(cls, path: Path) -> SklearnTextClassifier:
        import joblib

        d = joblib.load(path)
        return cls(d["name"], d["pipeline"])


class HFClassifier:
    """Enveloppe d'un modèle Hugging Face de classification de texte."""

    def __init__(self, model_name: str, device: str = "cpu", positive_labels: Sequence[str] = ("INJECTION", "LABEL_1", "injection", "1", "JAILBREAK")) -> None:
        from transformers import pipeline  # import paresseux : dépendance optionnelle

        self.name = f"hf:{model_name}"
        self._positive = {p.lower() for p in positive_labels}
        self._pipe = pipeline(
            "text-classification",
            model=model_name,
            device=-1 if device == "cpu" else device,
            truncation=True,
            max_length=512,
            top_k=None,
        )

    def predict_proba(self, texts: Sequence[str]) -> list[float]:
        if not texts:
            return []
        out = self._pipe(list(texts))
        scores: list[float] = []
        for item in out:
            entries = item if isinstance(item, list) else [item]
            pos = [e["score"] for e in entries if str(e["label"]).lower() in self._positive]
            scores.append(float(max(pos)) if pos else 0.0)
        return scores


def load_classifier() -> Classifier | None:
    """Charge le classifieur disponible, sinon ``None`` (mode dégradé).

    Ordre : modèle Hugging Face si ``GUARD_A_MODEL`` est défini, puis artefact
    TF-IDF entraîné localement (``python -m evaluation.train_classifier``).
    """
    model_name = os.environ.get("GUARD_A_MODEL", "").strip()
    if model_name:
        try:
            return HFClassifier(model_name, device=os.environ.get("GUARD_A_DEVICE", "cpu"))
        except Exception as exc:  # noqa: BLE001 - toute panne => repli, jamais un crash
            log.warning("Modèle HF %s indisponible (%s) : repli", model_name, exc)
    best = BEST_MODEL_PATH
    if best.exists():  # meilleur modèle retenu par ``python -m evaluation.select_best_model``
        try:
            return SklearnTextClassifier.load(best)
        except Exception as exc:  # noqa: BLE001
            log.warning("Meilleur modèle illisible (%s) : repli sur TF-IDF", exc)
    path = Path(os.environ.get("GUARD_A_TFIDF_PATH", DEFAULT_MODEL_PATH))
    if path.exists():
        try:
            return TfidfClassifier.load(path)
        except Exception as exc:  # noqa: BLE001
            log.warning("Artefact TF-IDF illisible (%s) : mode dégradé", exc)
    return None
