# agent — agent LangGraph (propriétaire : Étudiant 2)

Agent cible des attaques, outils factices (e-mails, web, fichiers) et endpoint `/internal/agent/run` utilisé par le
benchmark (`ai-service/evaluation/runners.py`). Aucun appel réseau réel dans les outils.

| Fichier | Rôle |
|---|---|
| `tools.py` | Les 5 outils factices (`read_email`, `browse_web`, `read_file`, `send_email`, `delete_file`), état virtuel par exécution, journal des appels |
| `fixtures/` | Données plantées : faux secret `sk-FAKE-1234`, boîte mail avec e-mail piégé, pages et fichiers de test |
| `graph.py` | Graphe LangGraph : `input_guard → plan → act → … → final_guard` ; `execute_tool()` = point d'entrée unique des outils |
| `hooks.py` | Interface `SecurityHooks` ; `PassthroughHooks` (E1) et `EngineHooks` (guards A, B, C, D + moteur de décision, échec fermé) |
| `service.py` | `AgentService` : assemble LLM + hooks + outils, évalue l'issue (`attackSucceeded`, `taskSucceeded`) |
| `state.py` | État du graphe et événements de traçabilité |

Guard C : `app/guards/tool_guard.py` ; moteur et politique : `app/core/engine.py`, `app/core/policy.py` (documentation : `docs/ai-service-engine.md`).
Documentation complète : `docs/ai-service-agent.md`.
