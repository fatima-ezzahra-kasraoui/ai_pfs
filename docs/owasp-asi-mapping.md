# Correspondance menaces AgentShield ↔ OWASP Top 10 for Agentic Applications (AS-S1-013)

**Source vérifiée le 2026-11-16** : liste ASI01–ASI10 relevée sur une page de synthèse
([Giskard](https://www.giskard.ai/knowledge/owasp-top-10-for-agentic-application-2026)), qui indique une publication en
**décembre 2025**. *À faire avant dépôt du rapport : confirmer intitulés et numérotation sur le PDF officiel OWASP GenAI
Security Project* (non consulté ici) et citer la version exacte.

| ID | Intitulé | Couvert par AgentShield ? | Où |
|---|---|---|---|
| ASI01 | Agent Goal Hijack | **Oui — cœur du projet** | Injection directe (Guard A) et indirecte (Guard B) ; cohérence action/demande (Guard C) |
| ASI02 | Tool Misuse and Exploitation | **Oui** | Liste blanche, niveau de risque, confirmation humaine (Guard C + moteur) |
| ASI03 | Identity and Privilege Abuse | Partiel | Rôles ADMIN/ANALYST côté backend ; pas de gestion d'identité de l'agent |
| ASI04 | Agentic Supply Chain Vulnerabilities | Non | Hors périmètre (dépendances, outils tiers) |
| ASI05 | Unexpected Code Execution (RCE) | Partiel | `execute_shell` refusé par la liste blanche ; aucune exécution de code dans le périmètre |
| ASI06 | Memory & Context Poisoning | Partiel | Le contenu externe est nettoyé et isolé (`<untrusted_content>`) ; pas de mémoire persistante de l'agent |
| ASI07 | Insecure Inter-Agent Communication | Non | Un seul agent |
| ASI08 | Cascading Failures | Partiel | Mode dégradé explicite des guards (`degraded`), échec fermé de l'API |
| ASI09 | Human-Agent Trust Exploitation | Partiel | Confirmation humaine pour les actions sensibles ; pas d'analyse de la persuasion de l'agent |
| ASI10 | Rogue Agents | Non | Hors périmètre |

Les fuites de données (Guard D) se rattachent surtout à OWASP LLM *Sensitive Information Disclosure* (série LLM Top 10),
et partiellement à ASI02. Ce rattachement est une interprétation de l'équipe, à valider avec l'encadrant.

Règle de rédaction : ne revendiquer que « Oui » et « Partiel » ci-dessus, avec la mention de ce qui n'est pas couvert.
