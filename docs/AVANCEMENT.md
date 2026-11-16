# AgentShield AI — Avancement et guide d'équipe

*Rédigé par Fati (Étudiant 1 — AI Security & Detection). À mettre à jour à chaque PR.*

## 1. Ce qui est réalisé (Étudiant 1, sprints 1 à 4)

| Domaine | Statut | Emplacement |
|---|---|---|
| Contrat `Verdict` (+ JSON Schema) | Fait | `ai-service/app/models/verdict.py`, `docs/contract/verdict.schema.json` |
| Guard A — entrée (injection directe, jailbreak, FR/EN, évasions Unicode/leetspeak) | Fait | `ai-service/app/guards/input_guard.py`, `rules.py` |
| Guard B — contenu externe (sanitizer HTML/Markdown, isolation `<untrusted_content>`) | Fait | `content_sanitizer.py`, `content_guard.py` |
| Guard D — sortie (secrets, Luhn, IBAN, e-mail, téléphone, canary `sk-FAKE-1234`) | Fait | `output_guard.py` |
| API `POST /internal/security/analyze`, `GET /internal/metrics` | Fait | `ai-service/app/api/` |
| Datasets, splits train/validation/test (graine 42, SHA-256), exemples français | Fait | `ai-service/evaluation/data/` |
| Métriques, benchmark E1/E2/E3, ablation, réglage de seuils, régression | Fait | `ai-service/evaluation/` |
| Scripts d'attaque (4 familles) + dataset | Fait | `ai-service/evaluation/attacks/` |
| Mapping OWASP ASI, ADR classifieur, analyse d'erreurs, rapport, recette | Fait | `docs/` |
| Frontend : Login, Overview, Audit Trail (lecture seule), Settings, Detection Analytics | Fait | `frontend/src/` |
| CI (secrets, ruff + pytest + régression, lint/test/build frontend) | Fait | `.github/workflows/ci.yml` |

Qualité : 177 tests Python, 45 tests frontend, ruff, tsc, eslint et scan de secrets, tous verts en CI.

## 2. Ce qui n'est PAS fait (à faire par les autres)

| Pour | À faire |
|---|---|
| **É2** | Agent LangGraph + outils factices (`ai-service/app/agent/`), Guard C (cohérence/outils), moteur de décision (`ai-service/app/engine/`, lit `config/policy.yaml`), endpoint `/internal/agent/run` |
| **É3** | Backend Spring Boot (`backend/`) : auth cookie HttpOnly + CSRF, rôles, persistance, audit, proxy vers `ai-service`, OpenAPI |
| **Équipe** | Geler les seuils, lancer la campagne officielle sur le test, docker-compose, PR de jonction |

## 3. Règles du jeu

- **Les guards ne décident jamais.** Ils renvoient un `Verdict` (score ∈ [0,1], `attackType`, `riskLevel`, `decision = None`). Seul le moteur (É2) produit ALLOW / SANITIZE / CONFIRM / BLOCK.
- **Fail-closed** : si le service IA est en erreur, le backend bloque, il n'autorise pas.
- **Aucun chiffre inventé.** Précision, rappel, ASR et latence viennent uniquement de `ai-service/evaluation/results/` (script + date + commit). Sans résultat, l'UI affiche « Évaluation à venir ».
- **Le jeu test n'est jamais lu pour régler quoi que ce soit.** `run_benchmark --split test` est refusé sans seuils gelés ET agent réel.
- **Pas de secret dans le dépôt** (le scanner de la CI échoue sinon), pas de texte brut utilisateur dans les logs.
- Tout mock est marqué `TEMPORARY`.
- Modifier le contrat `Verdict` : PR relue par É2 et É3, nouveau tag `contract-vX.Y`.

## 4. Comment s'intégrer (par rôle)

**Étudiant 2 (agent + moteur)**
1. Appeler les guards : `InputGuard().check({"text": ...})`, `ContentGuard().check({"text": ...})`, `OutputGuard().check({"text": ...})`, ou via `POST /internal/security/analyze`.
2. Utiliser `verdict.cleaned` quand la décision est SANITIZE (contenu isolé ou secrets masqués).
3. Implémenter `/internal/agent/run` : le benchmark (`evaluation/runners.py`, `HTTPRunner`) l'appelle. Le contrat est à confirmer avec Fati avant de coder.
4. Remplacer le pipeline simulé (`evaluation/sim/`) en lançant `python -m evaluation.run_benchmark` avec le vrai agent.
5. Seuils : `ai-service/config/policy.yaml` (valeurs actuelles **TEMPORARY** : 0,9 / 0,5 / 0,4).

**Étudiante 3 (backend)**
1. Exposer les routes que le frontend consomme (provisoires, à valider) : `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`, `GET /api/dashboard/overview`, `GET /api/system/health`, `GET /api/events`, `GET /api/policy`, `GET /api/analytics/metrics`. Les types attendus sont dans `frontend/src/types.ts`.
2. Appeler `ai-service` avec l'en-tête `X-AI-Service-Key` (variable `AI_SERVICE_KEY`).
3. Authentification par cookie HttpOnly + en-tête CSRF dérivé du cookie `XSRF-TOKEN` (aucun token dans `localStorage`).
4. `/api/analytics/metrics` peut relayer `GET /internal/metrics` d'`ai-service`.

## 5. Démarrage rapide

```bash
# Service IA
cd ai-service && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
python -m evaluation.run_regression
uvicorn app.main:app --port 8000

# Frontend
cd frontend && npm install && npm run dev
npm test && npm run build
```

Variables : copier `.env.example` en `.env` (jamais commité).
Guard A avec modèle HF (optionnel) : `pip install -r requirements-ml.txt`, puis `GUARD_A_MODEL=...`. Sans modèle, le guard fonctionne en **mode dégradé** (règles seules), signalé dans le verdict.

## 6. Workflow Git

- Une branche par tâche (`feature/<prénom>-<tâche>`), puis une PR vers `main` avec le template `.github/pull_request_template.md`.
- Commits clairs, tâche référencée (`[AS-Sx-xxx]`). Voir `CONTRIBUTING.md`.
- La CI doit être verte avant fusion, avec au moins une relecture par un autre membre.

## 7. Limites connues

- Campagne officielle sur le **test non lancée** et seuils **non gelés** : tous les chiffres sont préliminaires (validation).
- Les ASR d'ablation (0,78 → 0,00) viennent d'un **agent simulé** : ce ne sont pas des résultats réels.
- Les scores sur la validation sont optimistes. Sur le jeu externe InjecAgent, Guard B (règles seules) a une précision de 1,0 et un **rappel d'environ 0,45**.
- Modèles Hugging Face et `deepset` non mesurés (pas de réseau pendant le développement). À faire pour améliorer le rappel (voir `docs/adr-002-classifier.md`).
- Contrats `/internal/agent/run` et `/api/*` provisoires.

## 8. Prochaines étapes

1. Aligner les contrats (agent, API) entre É1, É2 et É3.
2. É2 livre l'agent et le moteur ; É3 livre le backend.
3. Mesurer un classifieur HF, puis geler les seuils (`python -m evaluation.tune_thresholds --freeze`, tag `thresholds-frozen`).
4. Lancer la campagne officielle sur le test (E1/E2/E3 + ablation) avec l'agent réel.
5. Alimenter Detection Analytics avec les vrais résultats et finaliser le rapport (`docs/rapport/`).
