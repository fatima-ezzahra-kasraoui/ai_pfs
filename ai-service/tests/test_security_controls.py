"""AS-S1-008 : squelette FastAPI sécurisé (en-têtes, taille, documentation, santé, configuration)."""
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.guards.content_guard import ContentGuard
from app.guards.input_guard import InputGuard
from app.guards.output_guard import OutputGuard
from app.llm.providers.mock import SimulatedLLM
from app.main import create_app

KEY = "test-key-not-a-secret"
H = {"X-AI-Service-Key": KEY}


def make(tmp_path, **kw):
    return TestClient(create_app(Settings(service_key=KEY, **kw), {"A": InputGuard(), "B": ContentGuard(), "D": OutputGuard()}, tmp_path, llm=SimulatedLLM()))


def test_security_headers_on_every_response(tmp_path):
    for r in (make(tmp_path).get("/health"), make(tmp_path).post("/internal/security/analyze", json={})):
        assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
        assert r.headers["cache-control"] == "no-store" and r.headers["referrer-policy"] == "no-referrer"


def test_request_id_generated_or_sanitised(tmp_path):
    c = make(tmp_path)
    assert len(c.get("/health").headers["x-request-id"]) == 32
    assert c.get("/health", headers={"X-Request-ID": "ok-1.2_3"}).headers["x-request-id"] == "ok-1.2_3"
    forged = c.get("/health", headers={"X-Request-ID": "x\ninjection y"}).headers["x-request-id"]
    assert forged != "x\ninjection y" and len(forged) == 32


def test_oversized_body_rejected_with_413_before_processing(tmp_path):
    c = make(tmp_path, max_body_bytes=1000)
    r = c.post("/internal/security/analyze", headers=H, content=b"x" * 2000)
    assert r.status_code == 413 and r.json()["requestId"] and r.headers["x-content-type-options"] == "nosniff"


def test_docs_exposed_in_dev_hidden_in_production(tmp_path):
    assert make(tmp_path).get("/docs").status_code == 200
    prod = make(tmp_path, env="production", expose_docs=False)
    assert prod.get("/docs").status_code == 404 and prod.get("/openapi.json").status_code == 404


def test_health_is_public_and_has_no_secret(tmp_path):
    d = make(tmp_path).get("/health").json()
    assert d["status"] == "ok" and d["agent"]["available"] is True and d["agent"]["simulated"] is True and "stub" not in d
    assert KEY not in str(d) and set(d["degraded"]) == {"A", "B", "D"}


def test_settings_defaults_and_env(monkeypatch):
    assert Settings(service_key="k").llm.provider == "mock" and Settings(service_key="k").max_body_bytes == 1_048_576
    monkeypatch.setenv("AI_ENV", "production")
    monkeypatch.setenv("AI_SERVICE_KEY", "abc")
    monkeypatch.delenv("AI_EXPOSE_DOCS", raising=False)
    s = Settings.from_env()
    assert s.env == "production" and s.expose_docs is False and s.service_key == "abc"
    monkeypatch.setenv("AI_EXPOSE_DOCS", "true")
    assert Settings.from_env().expose_docs is True


def test_settings_repr_hides_llm_key():
    from app.llm import LLMConfig

    assert "topsecret" not in repr(Settings(service_key="k", llm=LLMConfig(api_key="topsecret")))


def test_existing_endpoints_unchanged(tmp_path):
    c = make(tmp_path)
    assert c.post("/internal/security/analyze", json={"module": "A", "text": "x"}).status_code == 401
    assert c.post("/internal/security/analyze", headers=H, json={"module": "A", "text": "x"}).json()["decision"] is None
    assert c.get("/internal/metrics", headers=H).json()["status"] == "not_available"


@pytest.mark.parametrize("method,path", [("get", "/internal/health"), ("post", "/internal/agent/run"), ("get", "/internal/metrics")])
def test_all_internal_routes_require_key(tmp_path, method, path):
    assert getattr(make(tmp_path), method)(path).status_code == 401
