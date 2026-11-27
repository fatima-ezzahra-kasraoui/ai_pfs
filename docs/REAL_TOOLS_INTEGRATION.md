# Real tools — initial read-only delivery
Opt-in overlay; existing compose commands still use simulation. E3 ordinary runs only, no fixtures/scenarios/benchmark goals or simulated approvals. E2 is not implemented in the supplied agent service. Real writes are disabled at graph entry; SMTP adapter exists for controlled operator tests only. No real deletion. File listing reuses read_file(path=list) to preserve policy contracts. The file mount is read-only. Only put synthetic files there. Web proxy supports only example.com, pins a public IPv4 address, validates TLS, rejects redirects, limits response size. No independent destination firewall is configured; do not expand to arbitrary URLs. Mailpit has no external relay configured. UI port is loopback only. Existing Ollama overlay still grants AI service network access; this is not a hardened production sandbox. Existing backend ports are unchanged. No per-user integration RBAC added. Do not use personal data.

## Windows installation
Back up changed files first (or copy the project excluding secrets to a private backup). Extract patch into project root. Keep .env and existing volumes.

```powershell
cd C:\Users\a\ai_pfs
docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.real-tools.yml --profile dev up -d --build ai-service mailpit real-web
docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.real-tools.yml --profile dev ps
```
Open http://localhost:8025 and http://localhost:5173. Seed a test message as operator (not agent approval):
```powershell
docker exec agentshield-ai-service-1 python -c "import smtplib; from email.message import EmailMessage; m=EmailMessage(); m['From']='operator@societe.test'; m['To']='demo@societe.test'; m['Subject']='Lab test'; m.set_content('Meeting at 10.'); s=smtplib.SMTP('mailpit',1025,timeout=10); s.send_message(m); s.quit()"
```
Verify message in Mailpit. In Workspace ask: Read the latest email; List files using read_file path list; Read demo.txt; Browse https://example.com/. Check inspector and actual tool execution. Guard decisions may refuse requests. Do not bypass them. Verify no deletion or send via agent. Direct adapter checks are not proof of agent security.

## Rollback
Stop overlay services with compose using all three files and `stop mailpit real-web`. Restore changed source files from backup. Run original two-file compose `up -d --build ai-service`. Do not run down -v.

## Validation
Local pytest tests/test_real_tools.py tests/test_agent_tools.py: 23 passed. Python compileall passed. Docker, SMTP, HTTP, PDF extraction, full LangGraph and frontend build not executed here. Mailpit image tag/healthcheck require local verification. Integration page and execution explorer unchanged. Secure approval and Guard A remediation remain outstanding. No real send exposed to agent until these are validated.
