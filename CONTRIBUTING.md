# Contribuer

## Branches
Un identifiant de tâche par branche, fusion dans `main` uniquement par Pull Request relue.

```
feature/AS-S2-008-guard-c-whitelist
fix/AS-S4-018-resume-hash
docs/AS-S4-024-readme
test/AS-S2-013-engine-tests
chore/AS-S1-005-compose
```

## Commits (Conventional Commits)
`type(portée): message [ID]` — types : `feat`, `fix`, `test`, `docs`, `refactor`, `chore`.
Message à l'impératif, 72 caractères au plus.
Exemple : `feat(guard-a): normaliser l'unicode [AS-S2-002]`

## Pull Requests
- Titre : `[AS-S2-008] Guard C : liste blanche et niveau de risque`
- Moins de 400 lignes si possible, une relecture obligatoire (revue circulaire : É1 relit É2, É2 relit É3, É3 relit É1).
- Tout changement d'OpenAPI ou de `Verdict` passe par une PR relue par É2 et É3 et incrémente le tag `contract-vX.Y`.

## Qualité
- Python : `ruff check .` et `pytest` doivent passer (CI).
- Frontend : `npm run lint`, `npm test`, `npm run build`.
- Aucun secret dans le code ou les journaux : `python scripts/scan_secrets.py` (hook pré-push et CI).
- Les données temporaires sont marquées `TEMPORARY` ; aucun chiffre non mesuré n'est affiché.
