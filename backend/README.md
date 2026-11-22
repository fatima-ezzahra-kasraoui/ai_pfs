# backend — Spring Boot (propriétaire : Étudiante 3)

Authentification (cookie HttpOnly + CSRF), rôles, persistance, journal d'audit, proxy vers `ai-service`.
Contrat des routes : `docs/contract/openapi-public.yaml` (AS-S1-003).

## Prérequis
JDK 21 et Maven 3.9+ (ou Docker, voir `docker-compose.yml` à la racine).

## Commandes
```bash
cd backend
mvn test        # JUnit + tests d'intégration PostgreSQL (Testcontainers : Docker Desktop doit tourner)
```
Lancer l'application **depuis l'IDE** : exécuter `TestAgentShieldApplication` (dossier `src/test`). Elle démarre un
PostgreSQL jetable via Testcontainers, sans configuration. Avec Docker Compose : voir `docker-compose.yml` à la racine.

```bash
curl localhost:8080/api/system/health # {"status":"UP"}
```

## Base de données
Schéma versionné par Flyway : `src/main/resources/db/migration/V1__init.sql` (users, simulations, events, approvals).
Les valeurs d'énumération (rôles, décisions, statuts…) sont protégées par des contraintes `CHECK`. Ne jamais modifier une
migration déjà fusionnée : ajouter `V2__...sql`.

## Structure (`ma.agentshield`)
`auth` · `events` · `approvals` · `simulations` · `analytics` · `audit` · `integration` (client du service IA) · `config` (`ApiError`, `GlobalExceptionHandler`, CORS).

## Conventions
- Toute erreur est renvoyée en `{status, code, message}` — jamais de trace ni de détail interne (détail dans les journaux serveur uniquement).
- Profils : `dev` (défaut), `test`. Les comptes de seed (AS-S1-018) n'existent qu'en `dev`.
- Variables : `CORS_ALLOWED_ORIGINS`, `AI_SERVICE_URL`, `AI_SERVICE_KEY` (voir `.env.example`).
