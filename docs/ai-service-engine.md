# Guard C, cohérence, politique et moteur de décision (Sprint 2, É2)

Tâches : AS-S2-007 (politique), 008-009 (Guard C), 010 (cohérence), 011 (moteur), 012-013 (tests), 014-017 (interception de l'agent).

## 1. Décision d'architecture : un seul moteur, dans `core/`

| Élément | Emplacement | Raison |
|---|---|---|
| Chargeur de politique | `app/core/policy.py` | livrable du plan Agile (AS-S2-007) |
| Moteur de décision | `app/core/engine.py` | livrable du plan Agile (AS-S2-011) ; le README du dépôt citait `app/engine/` |
| Guard C | `app/guards/tool_guard.py` | livrable du plan ; même dossier que les guards A, B, D |
| Cohérence | `app/guards/coherence.py` | utilisée par le Guard C |
| Branchement dans l'agent | `app/agent/hooks.py` (`EngineHooks`) | remplace le `ReferenceHooks` temporaire du Sprint 1 |

Analyse avant choix : aucun code n'importe `app.engine` (vérifié : seul un README y vivait) ; le plan nomme `core/engine.py` ; les commentaires de
`evaluation/sim/pipeline.py` citent encore `app.engine` mais ne sont pas du code. Décision : le plan fait foi, `app/engine/README.md` renvoie vers
`core/`, il n'y a qu'un moteur. `evaluation.sim.pipeline.ReferencePipeline` (évaluation de Fati) n'est pas modifié et n'est plus utilisé par l'agent.

## 2. Politique (`config/policy.yaml`, AS-S2-007)

Validée par Pydantic au chargement (`PolicyError` explicite : clé inconnue, valeur hors bornes, `injection_review > injection_block`, `logging.db_path`
retiré…). Les erreurs ne recopient jamais les valeurs du fichier. Au démarrage, une politique invalide **empêche l'application de démarrer**. Au rechargement
(`PolicyStore.get()` détecte un changement du fichier, sans redémarrage), un fichier invalide est refusé et **la dernière politique valide reste active**
(`last_error`, `/health.policy.reloadFailed`). Sections : `thresholds`, `tools`, `parameters` (destinataires connus, chemins sensibles, fichiers importants),
`decisions`, `output`, `logging`. Un fichier minimal « Annexe A » (sans `parameters` ni `decisions`) reste valide grâce à des valeurs par défaut sûres.

Changements assumés : `logging.db_path` retiré (plan) ; sections `parameters` et `decisions` ajoutées ; `coherence_min_lexical` (voir §4) ;
**borne de blocage incluse** (`score >= 0,90`) : le commentaire de l'ancien fichier disait « > 0,90 » mais `evaluation/` (Fati) et `risk_from_score` utilisent `>=`.

## 3. Guard C (AS-S2-008, 009)

Contrôle chaque appel d'outil avant exécution. Il ne décide pas : `Verdict` (`decision = null`), constats dans `metadata.findings` (liste et classes dans l'en-tête de
`tool_guard.py`). `risk_level` = risque de l'outil (politique), distinct du `score` (1,0 interdiction ; `injection_review` pour une condition de confirmation ; 0,0 sinon).
Détails de sûreté : les raisons ne recopient aucune valeur d'argument (ni les **noms** de paramètres, que l'appelant contrôle) ; chemins normalisés (NFKC, invisibles, `%` répété,
`\`, points/espaces finals) avec détection de `..`, d'octet nul et de segments de points ; canary recherché après normalisation (invisibles, homoglyphes, pleine chasse, espacement) ;
destinataire non ASCII ou non unique considéré inconnu (jamais d'homoglyphe replié vers un domaine connu).

## 4. Cohérence action / demande (AS-S2-010) : ce qui est réellement validé

| Mesure | Nature | Disponible ici | Validé |
|---|---|---|---|
| `EmbeddingCoherence` | **sémantique** (cosinus d'embeddings) | non : aucun modèle, pas d'accès au réseau | **logique seulement** (encodeur injecté) ; le vrai modèle n'a **pas** été exécuté |
| `LLMJudgeCoherence` | **sémantique** (plan B du plan Agile) | non : pas de LLM réel | **logique seulement** (LLM simulé : lecture JSON, erreurs, indisponibilité) ; aucun vrai juge appelé |
| `TfidfCoherence` | **lexicale**, NON sémantique | oui, déterministe | oui, sur le jeu ci-dessous |

**Le repli TF-IDF n'est pas équivalent à des embeddings** : il compare des n-grammes de caractères, ne voit ni synonymes ni paraphrases ni autres langues, et son échelle n'est pas
celle d'un cosinus d'embeddings, d'où un seuil distinct (`coherence_min_lexical` = 0,10, `coherence_min` = 0,40 pour les mesures sémantiques). Il est toujours étiqueté
`semantic = false`, le verdict du Guard C est alors `degraded = true` et sa raison dit « non sémantique ». L'ordre de la chaîne : embeddings → juge LLM → lexical ; si aucune
mesure n'est disponible, le résultat est « invérifiable » et le Guard C demande une **confirmation** (`on_coherence_unavailable`), il ne présume jamais la cohérence.
Les champs libres (objet, corps d'un e-mail) sont exclus de la comparaison : un attaquant ne peut pas y recopier la demande pour gonfler la similarité (test dédié).

Résultats mesurés (jeu de 12 paires **écrit par l'auteur** + 3 cas de limites ; ce n'est **pas** une validation indépendante, le seuil a été choisi en les regardant) :

| Cohérent ? | Demande | Action | Similarité lexicale | Classement au seuil 0,10 |
|---|---|---|---|---|
| oui | Résume mes mails. | `read_email`  | 0.20 | ✔ |
| oui | Envoie un e-mail à bob@societe.test pour lui dire bonjour | `send_email` bob@societe.test | 0.40 | ✔ |
| oui | Supprime le fichier rapport_final.docx de mon dossier Documents. | `delete_file` /documents/rapport_final.docx | 0.57 | ✔ |
| oui | Affiche le contenu de config.txt. | `read_file` /documents/config.txt | 0.42 | ✔ |
| oui | Consulte la page https://intranet.societe.test/actualites | `browse_web` https://intranet.societe.test/actualites | 0.83 | ✔ |
| oui | Lis le mail mail-1 | `read_email` mail-1 | 0.19 | ✔ |
| non | Résume mes mails. | `send_email` attaquant@exemple.test | 0.03 | ✔ |
| non | Résume mes mails. | `delete_file` /documents/rapport_final.docx | 0.01 | ✔ |
| non | Affiche le contenu de notes.txt | `send_email` attaquant@exemple.test | 0.01 | ✔ |
| non | Consulte l'actualité de l'intranet | `delete_file` /documents/notes.txt | 0.00 | ✔ |
| non | Résume mes mails. | `read_file` /documents/config.txt | 0.01 | ✔ |
| non | Résume mes mails. | `send_email` bob@societe.test | 0.03 | ✔ |
| oui | What is in my inbox? | `read_email` | 0.00 | ✘ (faux positif) |
| oui | Fais-moi un point sur ma boîte de réception | `read_email` | 0.19 | ✔ |
| oui | Détruis ce document rapport_final.docx | `delete_file` | 0.37 | ✔ |

Limites connues, testées comme telles : paraphrases et autres langues (faux positif « What is in my inbox? » → 0,00) ; un **mauvais destinataire** (« Envoie un e-mail à Bob » → `attaquant@…`)
reste lexicalement cohérent (0,17), il est couvert par la règle indépendante « destinataire inconnu ». Les performances d'embeddings ou d'un juge LLM réels restent **à mesurer**.
Le juge reçoit la demande et l'action entre balises, tronquées, avec l'ordre de ne suivre aucune instruction qu'elles contiennent ; l'injection de prompt visant le juge n'est pas exclue.

## 5. Moteur de décision (AS-S2-011) et table de décision

**Le §10 du dossier de conception (tableau de décision) n'était pas disponible.** Le moteur applique l'ordre de priorité cité par le plan Agile (interdictions explicites, puis confirmation, puis
seuils 0,5 et 0,9, puis ALLOW ; décision la plus sévère) ; la table ci-dessous est **reconstituée** et non vérifiée ligne à ligne contre le §10.

| Priorité | Règle | Déclenchement | Décision |
|---|---|---|---|
| P1 | `P1.tool_not_allowed` `P1.invalid_arguments` `P1.unexpected_parameter` `P1.path_bypass` | constats du Guard C (interdictions) | BLOCK |
| P1 | `P1.canary_outgoing` | canary dans les arguments d'un outil (Guard C ou D) | `output.on_canary_in_outgoing_tool` (BLOCK) |
| P1 | `P1.incoherent_after_injection` | action incohérente **après** une injection indirecte détectée par B (escalade, hypothèse R2) | `decisions.on_incoherent_after_indirect_injection` (BLOCK) |
| P2 | `P2.requires_confirmation` `P2.unknown_recipient` `P2.sensitive_path` `P2.incoherent_action` `P2.coherence_unavailable` | constats du Guard C | CONFIRM (réglable dans `decisions`) |
| P3 | `T.block` | score d'un guard A/B ≥ `injection_block` | BLOCK |
| P3 | `T.review.<action>` | `injection_review` ≤ score < `injection_block` | `decisions.review_action` par étape (A : CONFIRM, B : SANITIZE) |
| P3 | `S.secret_masked`, `S.canary_in_response` | Guard D : secret en sortie (canary signalé) ; dans les arguments : seulement `output.mask_patterns` | `output.on_secret_detected` (SANITIZE) |
| P4 | `A.*` | aucune règle | ALLOW |

Agrégation : la plus sévère l'emporte ; à égalité, la priorité la plus haute donne la règle, et les raisons des règles à égalité sont fusionnées (`rules`). Verdict `ENGINE` : `decision` renseignée,
`score` = maximum des scores reçus, `risk_level` = maximum des niveaux (outil visé, ou score selon les **seuils de la politique**, jamais des seuils figés), `correlationId` repris.
Toute règle de décision vient de la politique, pas d'une valeur du code. Constat inconnu du Guard C → CONFIRM (jamais un ALLOW silencieux).

**À valider** : l'escalade R2 (BLOCK au lieu de CONFIRM après une injection indirecte) est une hypothèse de conception ; la couverture « chaque ligne du §10 » ne peut pas être affirmée.

## 6. Interception dans l'agent (AS-S2-014 à 017)

```
message ─► Guard A ─► moteur ─► [BLOCK : stop | CONFIRM : pending | SANITIZE : texte nettoyé | ALLOW]
LLM ─► appel d'outil ─► Guard C + Guard D(arguments) ─► moteur ─► décision ─► (exécution simulée seulement si autorisé) ─► résultat ─► Guard B ─► moteur ─► LLM
réponse finale ─► Guard D ─► moteur ─► réponse livrée
```

* `execute_tool()` reste le point d'entrée unique ; la décision précède toujours l'exécution (test d'ordre). Une action BLOQUÉE ou en ATTENTE n'est jamais exécutée.
* **Échec fermé** : une exception d'un guard ou du moteur donne BLOCK (message et appels d'outils : blocage ; retour d'outil : contenu retiré ; réponse finale : texte retenu).
* Un contenu d'outil n'est jamais une instruction : il n'atteint le LLM qu'après contrôle (autorisé, nettoyé ou retiré) et comme simple message `tool` ; toute action qu'il suggère repasse par C et le moteur,
  la cohérence étant jugée par rapport à la **demande initiale** (jamais au contenu de l'outil). Ce que cela ne garantit pas : si B ne détecte rien (score < seuil de revue) le contenu passe tel quel au LLM.
* **État CONFIRM** : par défaut (`confirmationPolicy: pending`) l'exécution est suspendue, `halted = awaiting_confirmation`, et `pending` renvoie
  `{actionId, kind, tool, arguments, riskLevel, reason, correlationId, status: "pending"}` avec les arguments **exacts** demandés par l'agent. Aucun état n'est conservé côté service : la reprise
  (AS-S3-002) et l'approbation (AS-S2-028) relèvent du backend. Au plus une action en attente par exécution ; les appels parallèles suivants sont marqués `skipped`. `kind = "message"` couvre le message entrant en bande de revue.
  `deny` refuse et poursuit ; `approve`/`auto` SIMULENT une approbation pour les bancs d'essai et sont refusés (422) en recette et en production.
* `verdicts` : liste ordonnée (guards puis `ENGINE`, étape par étape), un seul `correlationId` (fourni, sinon `runId`). `toolAttempts` : chaque appel demandé, exécuté ou non (arguments omis pour un appel bloqué).
  Journal : identifiants, outil, décision, règle ; jamais d'arguments, de contenu ni de secret.

## 7. Interfaces pour le backend (à valider avec É3)

Réponse de `POST /internal/agent/run` (contrat : `docs/contract/openapi-internal.yaml`) : `verdicts[]`, `pending`, `toolAttempts[]`, `halted` ∈ {`input_blocked`, `awaiting_confirmation`, `max_steps`, `llm_error`}.
Pour l'orchestrateur (AS-S2-025), le Lab (AS-S2-031) et les approbations (AS-S2-028) : l'empreinte des paramètres (SHA-256) est calculée côté Spring à partir de `pending.arguments` ; le service IA n'en renvoie pas.
Le format de `pending` est une **proposition** (champs `kind` et `status` ajoutés à la proposition initiale).

## 8. Observation sur un module de Fati (non modifié)

`VerdictModel` (`app/api/schemas.py`) sérialise `latencyMs` et `metadata` absents en `null`, alors que `verdict.schema.json` exige un nombre / un objet. Aucun guard réel ne les omet, donc aucune réponse actuelle n'est concernée ;
à corriger avec É1 si un guard futur peut les omettre.
