"""AS-S1-009 : configuration, clients HTTP (transport simulé, aucun réseau) et LLM simulés."""
import json

import httpx
import pytest

from app.llm import (
    LLMConfig,
    LLMConfigError,
    LLMProviderError,
    LLMResponseError,
    LLMTimeoutError,
    Message,
    ToolCall,
    ToolSpec,
    build_client,
)
from app.llm.providers.anthropic import AnthropicClient
from app.llm.providers.mock import ScriptedLLM, SimulatedLLM
from app.llm.providers.openai_compat import OpenAICompatibleClient

SPEC = ToolSpec("read_file", "Lit un fichier", {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]})
KEY = "k-not-a-real-secret"


def cfg(**kw):
    base = dict(provider="anthropic", model="m", api_key=KEY, max_retries=0)
    base.update(kw)
    return LLMConfig(**base)


def client_for(cls, config, handler):
    return cls(config, httpx.MockTransport(handler), sleep=lambda s: None)


# ------------------------------------------------------------------ configuration
def test_default_config_is_mock_and_valid():
    c = LLMConfig.from_env({})
    c.validate()
    assert c.provider == "mock" and c.public()["simulated"] is True


def test_from_env_reads_variables():
    c = LLMConfig.from_env({"LLM_PROVIDER": "Anthropic", "LLM_MODEL": "x", "LLM_API_KEY": KEY, "LLM_TIMEOUT_S": "5", "LLM_MAX_TOKENS": "99", "LLM_MAX_RETRIES": "2"})
    assert (c.provider, c.model, c.timeout_s, c.max_tokens, c.max_retries) == ("anthropic", "x", 5.0, 99, 2)


@pytest.mark.parametrize("env", [{"LLM_PROVIDER": "inconnu"}, {"LLM_PROVIDER": "anthropic", "LLM_MODEL": "m"}, {"LLM_PROVIDER": "anthropic", "LLM_API_KEY": "k"}, {"LLM_PROVIDER": "openai_compatible", "LLM_MODEL": "m"}, {"LLM_TIMEOUT_S": "0"}])
def test_invalid_config_fails_closed(env):
    with pytest.raises(LLMConfigError):
        LLMConfig.from_env(env).validate()


def test_non_numeric_value_rejected():
    with pytest.raises(LLMConfigError):
        LLMConfig.from_env({"LLM_TIMEOUT_S": "abc"})


def test_api_key_never_exposed():
    c = cfg()
    assert KEY not in repr(c) and KEY not in str(c.public())


def test_build_client_selects_provider():
    assert isinstance(build_client(LLMConfig()), SimulatedLLM)
    assert isinstance(build_client(cfg()), AnthropicClient)
    assert isinstance(build_client(cfg(provider="openai_compatible", base_url="http://localhost:11434/v1", api_key="")), OpenAICompatibleClient)
    with pytest.raises(LLMConfigError):
        build_client(cfg(api_key=""))


# ------------------------------------------------------------------ Anthropic
def test_anthropic_request_and_text_response():
    seen = {}

    def handler(request):
        seen["headers"], seen["body"], seen["url"] = request.headers, json.loads(request.content), str(request.url)
        return httpx.Response(200, json={"content": [{"type": "text", "text": "Bonjour"}], "stop_reason": "end_turn", "usage": {"input_tokens": 3, "output_tokens": 2}})

    out = client_for(AnthropicClient, cfg(), handler).complete("sys", [Message("user", "salut")], [SPEC])
    assert out.text == "Bonjour" and out.usage == {"input_tokens": 3, "output_tokens": 2}
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["headers"]["x-api-key"] == KEY and seen["headers"]["anthropic-version"]
    assert seen["body"]["system"] == "sys" and seen["body"]["tools"][0]["input_schema"] == SPEC.parameters
    assert seen["body"]["messages"] == [{"role": "user", "content": "salut"}]


def test_anthropic_tool_use_and_tool_result_wire_format():
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"content": [{"type": "tool_use", "id": "t1", "name": "read_file", "input": {"path": "/a"}}], "stop_reason": "tool_use"})

    c = client_for(AnthropicClient, cfg(), handler)
    out = c.complete("s", [Message("user", "lis")], [SPEC])
    assert out.tool_calls == (ToolCall("t1", "read_file", {"path": "/a"}),)
    c.complete("s", [Message("user", "lis"), Message("assistant", "", out.tool_calls), Message("tool", "contenu", tool_call_id="t1", name="read_file")], [SPEC])
    msgs = bodies[1]["messages"]
    assert msgs[1]["content"][0]["type"] == "tool_use" and msgs[2]["content"][0] == {"type": "tool_result", "tool_use_id": "t1", "content": "contenu"}


# ------------------------------------------------------------------ OpenAI-compatible
def test_openai_compatible_request_and_tool_calls():
    seen = {}

    def handler(request):
        seen["headers"], seen["body"], seen["url"] = request.headers, json.loads(request.content), str(request.url)
        return httpx.Response(200, json={"choices": [{"message": {"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "read_file", "arguments": "{\"path\": \"/a\"}"}}]}, "finish_reason": "tool_calls"}]})

    c = client_for(OpenAICompatibleClient, cfg(provider="openai_compatible", base_url="http://llm.local/v1/"), handler)
    out = c.complete("sys", [Message("user", "x")], [SPEC])
    assert out.tool_calls == (ToolCall("c1", "read_file", {"path": "/a"}),)
    assert seen["url"] == "http://llm.local/v1/chat/completions" and seen["headers"]["authorization"] == f"Bearer {KEY}"
    assert seen["body"]["messages"][0] == {"role": "system", "content": "sys"} and seen["body"]["tools"][0]["function"]["name"] == "read_file"


def test_openai_compatible_without_key_sends_no_authorization():
    seen = {}

    def handler(request):
        seen["h"] = request.headers
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client_for(OpenAICompatibleClient, cfg(provider="openai_compatible", base_url="http://x/v1", api_key=""), handler).complete("s", [Message("user", "x")])
    assert "authorization" not in seen["h"]


# ------------------------------------------------------------------ erreurs
def test_http_error_maps_to_provider_error_without_leaking_body():
    c = client_for(AnthropicClient, cfg(), lambda r: httpx.Response(401, text=f"bad key {KEY}"))
    with pytest.raises(LLMProviderError) as e:
        c.complete("s", [Message("user", "x")])
    assert e.value.status == 401 and KEY not in str(e.value) and "bad key" not in str(e.value)


def test_timeout_maps_to_timeout_error():
    def handler(request):
        raise httpx.ReadTimeout("t", request=request)

    with pytest.raises(LLMTimeoutError):
        client_for(AnthropicClient, cfg(), handler).complete("s", [Message("user", "x")])


def test_network_error_maps_to_provider_error():
    def handler(request):
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(LLMProviderError):
        client_for(AnthropicClient, cfg(), handler).complete("s", [Message("user", "x")])


@pytest.mark.parametrize("response", [httpx.Response(200, text="pas du json"), httpx.Response(200, json=[1]), httpx.Response(200, json={"content": "x"}), httpx.Response(200, json={"content": [{"type": "tool_use", "id": "1", "name": "n", "input": "pas un objet"}]})])
def test_malformed_response_raises_response_error(response):
    with pytest.raises(LLMResponseError):
        client_for(AnthropicClient, cfg(), lambda r: response).complete("s", [Message("user", "x")])


def test_openai_malformed_choices_and_arguments():
    for body in ({"choices": []}, {"choices": [{"message": {"tool_calls": [{"id": "1", "function": {"name": "n", "arguments": "{pas json"}}]}}]}):
        with pytest.raises(LLMResponseError):
            client_for(OpenAICompatibleClient, cfg(provider="openai_compatible", base_url="http://x"), lambda r, b=body: httpx.Response(200, json=b)).complete("s", [Message("user", "x")])


def test_retry_on_transient_status_then_success_and_exhaustion():
    calls = []

    def flaky(request):
        calls.append(1)
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]})

    assert client_for(AnthropicClient, cfg(max_retries=1), flaky).complete("s", [Message("user", "x")]).text == "ok" and len(calls) == 2
    calls.clear()
    with pytest.raises(LLMProviderError):
        client_for(AnthropicClient, cfg(max_retries=2), lambda r: (calls.append(1), httpx.Response(429))[1]).complete("s", [Message("user", "x")])
    assert len(calls) == 3


def test_no_retry_on_client_error():
    calls = []
    with pytest.raises(LLMProviderError):
        client_for(AnthropicClient, cfg(max_retries=3), lambda r: (calls.append(1), httpx.Response(400))[1]).complete("s", [Message("user", "x")])
    assert len(calls) == 1


# ------------------------------------------------------------------ simulation
def test_simulated_llm_is_flagged_and_deterministic():
    llm = SimulatedLLM()
    assert llm.simulated is True
    msgs = [Message("user", "Supprime le fichier rapport_final.docx de mon dossier Documents.")]
    a, b = llm.complete("s", msgs), llm.complete("s", msgs)
    assert a == b and a.tool_calls[0].name == "delete_file" and a.tool_calls[0].arguments == {"path": "/documents/rapport_final.docx"}


def test_scripted_llm_replays_and_records():
    s = ScriptedLLM([SimulatedLLM().complete("s", [Message("user", "Résume mes mails")])])
    s.complete("sys", [Message("user", "x")], [SPEC])
    assert s.calls[0][0] == "sys"
    with pytest.raises(LLMResponseError):
        s.complete("sys", [Message("user", "x")])


@pytest.mark.parametrize("text,path", [("Affiche le contenu de config.txt.", "/documents/config.txt"), ("Lis le fichier /documents/notes.txt, merci", "/documents/notes.txt"), ("contenu de dossier/a.b.txt!", "dossier/a.b.txt")])
def test_simulated_llm_file_name_ignores_trailing_punctuation(text, path):
    assert SimulatedLLM().complete("s", [Message("user", text)]).tool_calls[0].arguments == {"path": path}
