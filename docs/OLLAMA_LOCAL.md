# Ollama local (Windows / Docker Desktop)

Le compose standard reste en mode mock, réseau IA isolé. Le fichier supplémentaire active explicitement les modèles réels et un réseau sortant pour le service IA. Ce réseau n'est pas limité à Ollama : usage développement uniquement, pas de production. Aucun port IA supplémentaire n'est publié. Ne pas exposer Ollama sans authentification sur le LAN. Si Docker ne peut pas atteindre Ollama, vérifier Docker Desktop et le pare-feu avant de modifier son écoute.

Depuis la racine, PowerShell :

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
ollama list
Invoke-RestMethod http://localhost:11434/api/version
docker compose -f docker-compose.yml -f docker-compose.ollama.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.ollama.yml --profile dev up -d --build
```

Vérifier depuis le conteneur :

```powershell
docker compose exec ai-service python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/version', timeout=10).read().decode())"
docker compose exec ai-service python -c "from app.llm import LLMConfig, build_client, Message; c=build_client(LLMConfig.from_env()); print(c.complete('Answer briefly', [Message('user','What is prompt injection?')]).text)"
docker compose exec ai-service python -c "from app.core.config import Settings; from app.guards.coherence import default_checker; s=Settings.from_env(); c=default_checker(s.coherence_embedding_model, provider=s.coherence_embedding_provider, base_url=s.coherence_embedding_url, timeout_s=s.coherence_embedding_timeout_s); print(c.compare('Read the security report','Read the security report file'))"
```

Le dernier résultat doit avoir method='embeddings' et semantic=True. Le repli lexical existant reste disponible et signalé comme non sémantique ; il ne constitue pas une validation de Qwen. Les seuils existants sont inchangés et doivent être calibrés. La santé HTTP ne prouve pas la disponibilité des modèles. Tester ensuite un scénario complet et mesurer la latence, notamment lors des changements de modèle sur 8 Go de VRAM. Le backend peut avoir un délai inférieur à celui du LLM ; vérifier avant les scénarios longs.

Retour au mode mock : `docker compose -f docker-compose.yml up -d --force-recreate ai-service`.

Tests ciblés : `cd ai-service; python -m pytest tests/test_ollama_embedding.py tests/test_coherence.py tests/test_llm.py`.
