# Chapitre — Menaces, détection et évaluation (brouillon É1, AS-S4-005)

> Brouillon technique. Aucun chiffre n'y est saisi à la main : les valeurs se lisent dans `ai-service/evaluation/results/` et dans
> les tableaux générés (`python -m evaluation.make_tables`). Les chiffres de **validation** sont préliminaires ; la seule mesure à
> présenter comme résultat est la campagne **test** (seuils gelés, agent réel), non encore exécutée.

## 1. Menaces
Quatre familles, rattachées à l'OWASP Top 10 for Agentic Applications (voir `owasp-asi-mapping.md`) : injection directe
(ASI01), injection indirecte (ASI01), abus d'outil (ASI02), fuite de données (rattachée à *Sensitive Information Disclosure*).

## 2. Les guards d'É1
| Guard | Rôle | Principe | Limites connues |
|---|---|---|---|
| A | Injection directe / jailbreak | Normalisation Unicode (invisibles, homoglyphes, lettres espacées, leetspeak), règles FR/EN, classifieur optionnel, découpage en morceaux avec recouvrement | Détection par motifs : formulations nouvelles non couvertes ; classifieur TF-IDF écarté (FPR élevé sur la validation) |
| B | Injection indirecte | Nettoyage HTML/Markdown par analyseur (commentaires, CSS masqué, caractères invisibles), analyse du texte retiré, isolation `<untrusted_content>` | Rappel limité sur des injections anglaises (jeu externe InjecAgent) ; l'isolation ne garantit pas que l'agent n'obéisse pas |
| D | Fuite de données | Regex + validation Luhn / IBAN mod 97, canary token, masquage partiel, jamais de valeur brute dans le verdict | Pas de détection de noms sans Presidio (mode dégradé signalé) ; formats de secrets inconnus |
Un guard ne décide jamais : il renvoie un `Verdict` (module, score, type, raison). La décision appartient au moteur (É2).

## 3. Protocole d'évaluation
- Données : exemples français rédigés pour le projet (lots 1 et 2), séparés en train / validation / test, dédoublonnés avant découpage,
  graine fixe, manifeste avec empreintes SHA-256. Limite : même auteur, style homogène.
- Réglage : validation uniquement. Test jamais lu avant le gel des seuils ; `run_benchmark --split test` refuse de tourner sans seuils
  gelés ni agent réel.
- Configurations : E1 (sans protection), E2 (mots-clés + liste blanche), E3 (AgentShield complet) ; ablation A, A+B, A+B+C, tout.
- Métriques : ASR, précision, rappel, F1, FPR, utilité (tâches légitimes réussies), taux de confirmations, latence p50/p95.
- Biais assumés : le Guard C du banc local est minimal (sans similarité sémantique) ; l'agent du banc local est simulé et crédule.
  Les chiffres produits avec lui mesurent la couverture des guards, **pas** l'ASR d'un LLM réel.

## 4. À écrire après la campagne test
Tableau §26 (généré), analyse qualitative des échecs (liste générée dans `docs/resultats/failures_*.md`), comparaison E1/E2/E3 et
ablation, discussion des limites ci-dessus. Ne rien affirmer qui ne soit dans les fichiers de résultats.
