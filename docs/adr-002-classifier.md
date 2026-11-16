# ADR-002 — Classifieur du Guard A

*Document généré par `python -m evaluation.compare_classifiers --write-adr` à partir de
`evaluation/results/classifier_comparison_validation_20261115T235212Z.json` (commit `6e00dcbe`, graine 42). Ne pas éditer les chiffres à la main.*

## Contexte
Le Guard A doit détecter les injections directes et jailbreaks en français et en anglais, sans faux positifs
sur les requêtes normales (F02). Le dossier prévoit un modèle BERT/DeBERTa ajusté sur `deepset/prompt-injections`,
avec un modèle pré-entraîné Hugging Face en plan B.

## Protocole
Mêmes conditions pour tous les candidats : jeu de **validation** (30 messages, équilibré), seuil
`injection_review = 0.5`, entraînement sur le split *train* uniquement. Le split de test n'est pas lu.

## Résultats mesurés (validation)
| Candidat | Précision | Rappel | F1 | FPR | Latence p50 (ms) | Latence p95 (ms) |
|---|---|---|---|---|---|---|
| `rules` | 1.000 | 0.933 | 0.966 | 0.000 | 0.091 | 0.243 |
| `tfidf` | 0.812 | 0.867 | 0.839 | 0.200 | 1.177 | 1.506 |
| `rules+tfidf` | 0.833 | 1.000 | 0.909 | 0.200 | 1.229 | 1.383 |



## Décision (provisoire, calculée sur les chiffres ci-dessus)
Retenir **`rules`** : plus fort rappel (0.933) parmi les candidats dont le taux de faux positifs sur la validation ≤ 5 %. Écartés pour faux positifs excessifs : `tfidf` (FPR 0.200), `rules+tfidf` (FPR 0.200).

Cette décision **n'est pas définitive** : les modèles DeBERTa / pré-entraîné n'ont pas pu être mesurés dans cet environnement.
Avant de figer l'ADR, exécuter `python -m evaluation.compare_classifiers --hf-model <nom> --write-adr` sur une machine
avec accès à Hugging Face et trancher sur les chiffres obtenus, dans les mêmes conditions.
Le champ `degraded` du verdict signifie « aucun classifieur ML actif » : il reste à `true` tant qu'un classifieur n'est pas retenu.

## Limites
- La validation est petite ; les écarts de quelques points ne sont pas significatifs.
- Les règles ont été améliorées en examinant les erreurs de la validation puis du train (AS-S3-021) : les chiffres
  de validation sont donc optimistes. Seule la campagne sur le test, une fois les seuils gelés, est une mesure honnête.
- Les exemples français ont été rédigés pour le projet (relecture croisée à tracer en PR) et partagent un style.
