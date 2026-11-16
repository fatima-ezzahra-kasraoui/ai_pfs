# backend — Spring Boot (propriétaire : Étudiante 3)

Authentification (cookie HttpOnly + CSRF), rôles, persistance, journal d'audit, proxy vers `ai-service`.
Contrat des routes : `docs/contract/openapi-public.yaml` (AS-S1-003).

## Prérequis
JDK 21 et Maven 3.9+ (ou Docker, voir `docker-compose.yml` à la racine).

## Commandes
```bash
cd backend
mvn test                              # JUnit (gestionnaire d'erreurs, health)
mvn spring-boot:run                   # profil dev, http://localhost:8080
curl localhost:8080/api/system/health # {"status":"UP"}
```

## Structure (`ma.agentshield`)
`auth` · `events` · `approvals` · `simulations` · `analytics` · `audit` · `integration` (client du service IA) · `config` (`ApiError`, `GlobalExceptionHandler`, CORS).

## Conventions
- Toute erreur est renvoyée en `{status, code, message}` — jamais de trace ni de détail interne (détail dans les journaux serveur uniquement).
- Profils : `dev` (défaut), `test`. Les comptes de seed (AS-S1-018) n'existent qu'en `dev`.
- Variables : `CORS_ALLOWED_ORIGINS`, `AI_SERVICE_URL`, `AI_SERVICE_KEY` (voir `.env.example`).
