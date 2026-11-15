# AgentShield AI

Plateforme de détection, d'évaluation et de prévention des attaques ciblant les agents IA autonomes
(projet de fin de semestre, encadrant : M. Lachgar).

```
frontend/    React + TypeScript (aucune règle de sécurité)
backend/     Spring Boot (authentification, rôles, persistance, audit)      -> Étudiante 3
ai-service/  Python / FastAPI : guards A–D, moteur de décision, évaluation
docs/        contrats OpenAPI, ADR, recette
```

## Contenu de cette branche (Étudiant 1 — AI Security & Detection)

| Domaine | Emplacement |
|---|---|
| Modèle `Verdict` partagé | `ai-service/app/models/verdict.py` |
| Guard A (entrée) | `ai-service/app/guards/input_guard.py` |
| Guard B (contenu externe) | `ai-service/app/guards/content_sanitizer.py`, `content_guard.py` |
| Guard D (sortie / données) | `ai-service/app/guards/output_guard.py` |
| Endpoints `/internal/security/analyze`, `/internal/metrics` | `ai-service/app/api/` |
| Données, splits, exemples français | `ai-service/evaluation/data/` |
| Benchmark, métriques, ablation, seuils | `ai-service/evaluation/` |
| Pages Login, Overview, Audit Trail, Settings, Analytics | `frontend/src/pages/` |

Les éléments dont les autres membres sont propriétaires (agent LangGraph, Guard C, moteur de décision,
backend Spring) ne sont **pas** inclus : les guards ne dépendent que de l'interface `Verdict`.

## Démarrage rapide (service IA)

```bash
cd ai-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                       # tests unitaires
python -m evaluation.make_splits   # régénère les splits (graine fixe)
python -m evaluation.run_regression
uvicorn app.main:app --port 8000
```

Optionnel (qualité maximale) : `pip install -r requirements-ml.txt` puis définir `GUARD_A_MODEL`
(voir `docs/adr-002-classifier.md`). Sans modèle, le Guard A fonctionne en **mode dégradé** (règles seules),
signalé `degraded` dans le verdict.

## Frontend

```bash
cd frontend && npm install && npm run dev
npm test && npm run build
```

## Règle d'or : aucun chiffre inventé

Tous les chiffres (précision, rappel, ASR, latence…) sont produits par les scripts de
`ai-service/evaluation/` et écrits dans `ai-service/evaluation/results/` avec la date et le commit.
Tant qu'aucun résultat n'existe, l'interface affiche « Évaluation à venir ».

Voir `CONTRIBUTING.md` pour les branches, commits et Pull Requests.
