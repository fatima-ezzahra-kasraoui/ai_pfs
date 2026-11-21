"""Client Anthropic (API Messages) via HTTP direct : aucune dépendance SDK.

NON VALIDÉ contre le service réel (aucune clé disponible lors du développement) : le format est couvert
par des tests sur transport simulé uniquement (voir docs/llm.md).
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from ..config import LLMConfig
from ..errors import LLMResponseError
from ..types import LLMResponse, Message, ToolCall, ToolSpec
from .http_base import HTTPProvider

DEFAULT_BASE_URL = "https://api.anthropic.com"
API_VERSION = "2023-06-01"


def to_wire_messages(messages: Sequence[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "assistant":
            blocks: list[dict[str, Any]] = [{"type": "text", "text": m.content}] if m.content else []
            blocks += [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments} for c in m.tool_calls]
            out.append({"role": "assistant", "content": blocks or [{"type": "text", "text": ""}]})
        elif m.role == "tool":
            block = {"type": "tool_result", "tool_use_id": m.tool_call_id, "content": m.content}
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(block)  # résultats d'appels parallèles : un seul message utilisateur
            else:
                out.append({"role": "user", "content": [block]})
        elif m.role == "user":
            out.append({"role": "user", "content": m.content})
    return out


class AnthropicClient(HTTPProvider):
    name = "anthropic"

    def __init__(self, config: LLMConfig, transport: httpx.BaseTransport | None = None, **kw: Any) -> None:
        super().__init__(config, transport, **kw)
        self.url = (config.base_url or DEFAULT_BASE_URL).rstrip("/") + "/v1/messages"

    def complete(self, system: str, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.config.model, "max_tokens": self.config.max_tokens, "temperature": self.config.temperature,
            "system": system, "messages": to_wire_messages(messages),
        }
        if tools:
            body["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools]
        headers = {"x-api-key": self.config.api_key, "anthropic-version": API_VERSION, "content-type": "application/json"}
        data = self._post(self.url, headers, body)
        content = data.get("content")
        if not isinstance(content, list):
            raise LLMResponseError("anthropic : champ 'content' absent")
        text, calls = [], []
        for block in content:
            if not isinstance(block, dict):
                raise LLMResponseError("anthropic : bloc de contenu invalide")
            if block.get("type") == "text":
                text.append(str(block.get("text", "")))
            elif block.get("type") == "tool_use":
                args = block.get("input")
                if not isinstance(args, dict) or "id" not in block or "name" not in block:
                    raise LLMResponseError("anthropic : appel d'outil invalide")
                calls.append(ToolCall(str(block["id"]), str(block["name"]), args))
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return LLMResponse("".join(text), tuple(calls), str(data.get("stop_reason") or "end"), {k: v for k, v in usage.items() if isinstance(v, int)})
