# engine — renvoi (propriétaire : Étudiant 2)

Il n'y a **qu'un seul moteur de décision**, et il n'est pas dans ce répertoire (décision d'architecture du Sprint 2, `docs/ai-service-engine.md` §1) :

| Rôle | Emplacement |
|---|---|
| Moteur de décision (ALLOW / SANITIZE / CONFIRM / BLOCK) | `app/core/engine.py` |
| Chargement et validation de `config/policy.yaml` | `app/core/policy.py` |
| Guard C (appels d'outils) | `app/guards/tool_guard.py` |

Les guards ne décident jamais : ils renvoient un `Verdict` (`decision = None`) ; seul le moteur applique la politique.
