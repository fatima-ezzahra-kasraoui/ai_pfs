# agent — agent LangGraph (propriétaire : Étudiant 2)

Agent cible des attaques, outils factices (e-mails, web, fichiers) et endpoint `/internal/agent/run` utilisé par le
benchmark (`ai-service/evaluation/runners.py`). Aucun appel réseau réel dans les outils.

| Fichier | Rôle |
|---|---|
| `tools.py` | Les 5 outils factices (`read_email`, `browse_web`, `read_file`, `send_email`, `delete_file`), état virtuel par exécution, journal des appels |
| `fixtures/` | Données plantées : faux secret `sk-FAKE-1234`, boîte mail avec e-mail piégé, pages et fichiers de test |
| `graph.py` | Graphe LangGraph : `input_guard → plan → act → … → final_guard` ; `execute_tool()` = point d'entrée unique des outils |
| `hooks.py` | Interface `SecurityHooks` (points d'accroche guards / moteur) ; `PassthroughHooks` (E1) et `ReferenceHooks` (TEMPORAIRE) |
| `service.py` | `AgentService` : assemble LLM + hooks + outils, évalue l'issue (`attackSucceeded`, `taskSucceeded`) |
| `state.py` | État du graphe et événements de traçabilité |

Brancher le Guard C et le moteur d'É2 (Sprint 2) : implémenter `SecurityHooks` et le fournir à `AgentService._hooks`.
Documentation complète : `docs/ai-service-agent.md`.
