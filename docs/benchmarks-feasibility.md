# Faisabilité des benchmarks (AS-S1-014)

## InjecAgent — vérifié
- Dépôt : `uiuc-kang-lab/InjecAgent`, cloné en lecture seule ; commit **`f19c9f2c79a41046eb13c03c51a24c567a8ffa07`**.
- Licence : **MIT** (fichier `LICENCE`, copyright 2023 Qiusi Zhan). Réutilisation et citation autorisées.
- Contenu : `test_cases_dh_base.json` (510 cas, *direct harm*) et `test_cases_ds_base.json` (544 cas, *data stealing*) ;
  chaque cas porte l'instruction de l'attaquant, la réponse d'outil injectée et un gabarit de réponse bénigne.
- **Ce qui marche sans LLM** : mesurer la *détection* du Guard B sur la réponse d'outil injectée vs le gabarit vidé
  (`python -m evaluation.injecagent_guard_b --repo <clone>`). Fait ; résultat dans `evaluation/results/guard_b_injecagent_*.json`.
- **Ce qui exige un LLM** : l'ASR au sens InjecAgent (l'agent exécute-t-il l'outil de l'attaquant ?) nécessite un
  agent LLM branché sur les outils simulés. Non faisable dans l'environnement actuel (pas d'agent d'É2, pas de clé API).
  → l'ASR du rapport viendra de nos scénarios (`evaluation/attacks/dataset`) rejoués sur l'agent réel (`run_benchmark --agent http`).
- Décision : **ne pas recopier** les cas InjecAgent dans le dépôt ; les scénarios « maison » s'en inspirent (le champ `source`
  l'indique) et InjecAgent sert de **jeu externe de détection**, jamais utilisé pour régler les règles.

## Autres jeux
- `deepset/prompt-injections` (Hugging Face) : `fetch_datasets.py` est prêt mais **non exécuté** (pas d'accès à Hugging Face
  ici) ; licence à lire sur la carte du jeu avant citation.
- AgentDojo : **non évalué**. À examiner si le temps le permet ; aucune affirmation n'est faite à son sujet.

## Plan B documenté
Si l'agent réel d'É2 n'est pas prêt à temps : présenter la détection par guard (mesurée) et l'ablation, en indiquant que l'ASR de
bout en bout n'a pas été mesuré sur un LLM réel.
