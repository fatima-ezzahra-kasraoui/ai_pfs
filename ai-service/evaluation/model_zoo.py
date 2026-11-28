"""Zoo de classifieurs candidats pour le Guard A : 5 modèles scikit-learn + modèles Hugging Face optionnels.

Tous exposent ``predict_proba(texts) -> list[float]`` (protocole ``Classifier``). Les modèles
scikit-learn partagent les mêmes caractéristiques TF-IDF (mots + caractères) pour que la
comparaison porte sur l'algorithme et non sur la représentation.
"""
from __future__ import annotations

from collections.abc import Callable

from app.guards.classifier import SklearnTextClassifier


def _features():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import FeatureUnion

    return FeatureUnion(
        [
            ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True, strip_accents="unicode")),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True, strip_accents="unicode")),
        ]
    )


def _pipe(clf):
    from sklearn.pipeline import Pipeline

    return Pipeline([("features", _features()), ("clf", clf)])


def _logreg(seed: int):
    from sklearn.linear_model import LogisticRegression

    return _pipe(LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced", random_state=seed))


def _logreg_strong_reg(seed: int):
    from sklearn.linear_model import LogisticRegression

    return _pipe(LogisticRegression(max_iter=2000, C=0.5, class_weight="balanced", random_state=seed))


def _svm(seed: int):
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.svm import LinearSVC

    return _pipe(CalibratedClassifierCV(LinearSVC(C=1.0, class_weight="balanced", random_state=seed), cv=3))


def _nb(seed: int):  # noqa: ARG001
    from sklearn.naive_bayes import ComplementNB

    return _pipe(ComplementNB(alpha=0.3))


def _forest(seed: int):
    from sklearn.ensemble import RandomForestClassifier

    return _pipe(RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=seed, n_jobs=-1))


SKLEARN_CANDIDATES: dict[str, Callable[[int], object]] = {
    "tfidf-logreg": _logreg,
    "tfidf-logreg-C0.5": _logreg_strong_reg,
    "tfidf-linearsvm": _svm,
    "tfidf-complementnb": _nb,
    "tfidf-randomforest": _forest,
}


def train_sklearn(name: str, texts, labels, seed: int = 42) -> SklearnTextClassifier:
    pipe = SKLEARN_CANDIDATES[name](seed)
    pipe.fit(list(texts), list(labels))
    return SklearnTextClassifier(name, pipe)


# Modèles Hugging Face proposés (nécessitent requirements-ml.txt et un accès à huggingface.co).
HF_SUGGESTIONS = [
    "protectai/deberta-v3-base-prompt-injection-v2",  # DeBERTa-v3 spécialisé injection (anglais surtout)
    "leolee99/PIGuard",                                # PIGuard (MOF, moins de sur-défense)
    "meta-llama/Llama-Prompt-Guard-2-86M",             # Prompt Guard 2 (accès à accepter sur HF)
]
