# Service IA : agent, outils, LLM, stub (Sprint 1, É2)

## Vue d'ensemble

```
POST /internal/agent/run ──► AgentService ──► graphe LangGraph
                                               input_guard → plan(LLM) ⇄ act(outils) → final_guard
                                               │ hooks : Guard A │          │ C + D │ puis B │   D
```

* **Aucun contournement** : en mode protégé, les quatre points de contrôle (message, appel d'outil, contenu d'outil,
  réponse finale) sont toujours traversés (test `test_flow_always_traverses_every_hook_in_order`).
* **Les guards ne décident pas** : `ReferenceHooks` traduit leurs `Verdict` en ALLOW / SANITIZE / CONFIRM / BLOCK.
  Cette traduction est **TEMPORAIRE** : elle réutilise `evaluation.sim.pipeline.ReferencePipeline` (seuils de `policy.yaml`,
  Guard C minimal). Le vrai Guard C et le moteur de décision (Sprint 2) s'y branchent en implémentant `SecurityHooks`.
* **CONFIRM** : pas d'humain en ligne au Sprint 1. `confirmationPolicy` : `deny` (défaut), `approve`, `auto`
  (humain simulé : refuse si un `attackGoal` est connu, approuve sinon).

## Outils factices (`app/agent/tools.py`)

| Outil | Paramètres | Effet simulé |
|---|---|---|
| `read_email` | `email_id?` | lit la boîte virtuelle |
| `browse_web` | `url` (http/https) | pages de démonstration uniquement, aucun réseau |
| `read_file` | `path` | système de fichiers virtuel (contient le faux secret `sk-FAKE-1234`) |
| `send_email` | `to`, `subject?`, `body?` | enregistré dans une boîte d'envoi en mémoire |
| `delete_file` | `path` | retiré de la copie en mémoire de l'exécution |

Les données plantées (faux secret, boîte mail avec e-mail piégé `mail-3`, pages et fichiers) sont dans `app/agent/fixtures/`.
L'e-mail piégé n'est pas listé par défaut (`read_email` sans identifiant) pour que « Résume mes mails » reste un usage légitime ; il est lu par
identifiant ou listé avec `ToolBox(trapped_inbox=True)`. Chaque appel est consigné dans `ToolBox.call_log` (réussi ou non, toujours simulé).

Garanties : aucun accès disque/réseau/SMTP, état recréé à chaque exécution, chemins `..`/NUL rejetés, paramètres inconnus refusés.
**Hypothèse à valider** : les noms viennent de `policy.yaml` (Annexe A) ; les paramètres sont déduits des scénarios du dossier,
le dossier de conception v3.0 n'étant pas disponible lors du développement.

## LLM (`app/llm/`)

| Élément | Fichier |
|---|---|
| Configuration (`LLM_*`) | `config.py` : clé jamais affichée (`repr`, `/health`, journaux) |
| Interface et fabrique | `client.py` (`LLMClient`, `build_client`) |
| Types neutres | `types.py` (aucun SDK) |
| Erreurs | `errors.py` (jamais de clé ni de corps de réponse dedans) |
| Fournisseurs réels | `providers/anthropic.py`, `providers/openai_compat.py` (HTTP direct, délais, 1 nouvelle tentative sur 408/429/5xx) |
| Cache (reproductibilité, mode hors ligne) | `cache.py` : `CachedLLM(inner, chemin, offline=False)` rejoue les réponses par empreinte de requête ; hors ligne, une requête inconnue échoue au lieu d'appeler le réseau |
| Simulation | `providers/mock.py` : `SimulatedLLM` (agent crédule déterministe), `ScriptedLLM` (tests) |

`LLM_PROVIDER=mock` par défaut : aucun réseau, aucune clé. Une configuration réelle invalide désactive **seulement l'agent**
(503 sur `/internal/agent/run`, `/health.agent.available=false`) ; les guards restent disponibles.

### Ce qui est validé et ce qui ne l'est pas

* **Validé (tests automatiques)** : configuration, formats de requête/réponse des deux fournisseurs sur transport HTTP
  simulé, mapping des erreurs, nouvelles tentatives, absence de fuite de clé.
* **NON validé** : aucun appel à un vrai modèle (pas de clé ni d'accès réseau). Le **choix du LLM** (AS-S1-009) n'est pas
  tranché ici : le dossier de conception n'était pas disponible, aucun modèle n'est imposé (`LLM_MODEL` obligatoire).
  Les critères de comparaison et la validation sur un modèle réel restent à faire par l'équipe.
* `SimulatedLLM` obéit à toute instruction lue : ses résultats mesurent la couverture des guards, **pas** l'ASR d'un vrai LLM.

## Stub (`app/stub/`) : AS-S1-010

Activation : **`AI_STUB=true`** sur `app.main:app` (ou `uvicorn app.stub.app:app`). Mêmes routes, schémas, authentification et codes que le
service réel : les guards sont remplacés par de faux guards déterministes (`app/stub/guards.py`) et le LLM par `SimulatedLLM`.
Il ne détecte rien : score 0 sauf marqueur explicite `[[stub:score=0.95]]` dans le texte ; verdicts `degraded=true`,
`metadata.stub=true`, raison préfixée `[STUB]`. Toute réponse porte l'en-tête **`X-Stub: true`** et `/internal/health` renvoie `stub: true`.
**Le stub ne peut pas être actif en profil de recette ou de production** : `AI_STUB=true` avec `AI_ENV=recette|production` fait échouer le
démarrage (`StubForbiddenError`). `/internal/metrics` répond « Évaluation à venir » (aucun chiffre factice).

## Sécurité du service (AS-S1-008)

Clé de service obligatoire et échec fermé (existant) · `GET /internal/health` protégé par la clé (sans clé : 401) et `GET /health` public pour le
healthcheck Docker Compose · `X-Correlation-ID` propagé (journal d'accès, réponse, `correlationId` de l'agent) · format d'erreur commun
`{status, code, message, detail, requestId}` (surensemble de l'`ApiError` Spring) ; les erreurs de validation ne renvoient jamais la valeur reçue · identifiant de requête assaini (`X-Request-ID`) · limite de taille
(413 sur `Content-Length`) · en-têtes `nosniff`, `X-Frame-Options`, `no-referrer`, `no-store` · `/docs` désactivé en production ·
erreurs 500 génériques (détail uniquement dans le journal) · journaux sans message, contenu d'outil, réponse ni secret ·
validation stricte (`extra=forbid`, bornes, motifs) · exécution bornée (`AGENT_MAX_STEPS`).
Limite connue : la taille n'est contrôlée que si `Content-Length` est présent ; à doubler par la limite du reverse proxy.

## Point d'entrée unique des outils

Tout appel d'outil passe par `agent.graph.execute_tool()` (contrôle de l'appel → exécution → contrôle du résultat). Deux tests le garantissent :
espion à l'exécution sur `ToolBox.execute` et analyse statique (AST) de `app/`.

## Contrat

`docs/contract/openapi-internal.yaml` (OpenAPI 3.1) : les cinq endpoints internes du §20.3 (`/internal/health`, `/internal/security/analyze`,
`/internal/agent/run`, `/internal/metrics` et `/internal/approvals/{id}/resume`, ce dernier documenté mais `x-status: planned` jusqu'à AS-S3-002). Validation : `python scripts/validate_openapi.py` et
`pytest tests/test_openapi_contract.py` (spec valide, mêmes routes/champs que FastAPI, réponses réelles conformes, `Verdict` identique au schéma partagé).
