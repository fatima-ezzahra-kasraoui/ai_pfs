#!/usr/bin/env bash
# Smoke test (AS-S1-005) : verifie l'etat des services de la stack Compose.
#   ./scripts/smoke.sh
# Code de sortie 0 = tout est conforme.
set -u

cd "$(dirname "$0")/.."
fail=0
ok()  { printf '  [OK]   %s\n' "$1"; }
ko()  { printf '  [FAIL] %s\n' "$1"; fail=1; }

state() { docker compose ps --format '{{.Service}} {{.Health}}' 2>/dev/null | awk -v s="$1" '$1==s {print $2}'; }

echo "== Etat de sante des conteneurs =="
for svc in postgres ai-service backend; do
  [ "$(state "$svc")" = "healthy" ] && ok "$svc healthy" || ko "$svc non healthy ($(state "$svc"))"
done

echo "== Endpoints health =="
code=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/api/system/health || true)
[ "$code" = "200" ] && ok "backend GET /api/system/health -> 200" || ko "backend /api/system/health -> $code"

echo "== Isolation reseau =="
# ai-service et postgres ne doivent publier aucun port sur l'hote.
for svc in ai-service postgres; do
  published=$(docker compose ps --format '{{.Service}} {{.Publishers}}' | awk -v s="$svc" '$1==s' | grep -c 'PublishedPort":[1-9]' || true)
  [ "$published" = "0" ] && ok "$svc non expose a l'hote" || ko "$svc expose a l'hote"
done
if curl -s -m 2 -o /dev/null http://localhost:8000/health; then ko "ai-service repond sur localhost:8000"; else ok "ai-service injoignable depuis l'hote"; fi

echo "== Erreurs sans detail interne =="
body=$(curl -s http://localhost:8080/api/does-not-exist || true)
case "$body" in
  *'"code"'*) ok "format d'erreur JSON {status, code, message}" ;;
  *) ko "format d'erreur inattendu: $body" ;;
esac
case "$body" in *stackTrace*|*"at ma.agentshield"*) ko "trace interne exposee" ;; *) ok "aucune trace interne" ;; esac

echo
[ "$fail" = 0 ] && echo "Smoke test : SUCCES" || echo "Smoke test : ECHEC"
exit "$fail"
