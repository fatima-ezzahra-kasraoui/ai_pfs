"""Client « OpenAI-compatible » (``/chat/completions``) : couvre OpenAI, vLLM, Ollama, LM Studio, etc.

NON VALIDÉ contre un service réel (aucun accès pendant le développement) : tests sur transport simulé.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import httpx

from ..config import LLMConfig
from ..errors import LLMResponseError
from ..types import LLMResponse, Message, ToolCall, ToolSpec
from .http_base import HTTPProvider


def to_wire_messages(system: str, messages: Sequence[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for m in messages:
        if m.role == "assistant":
            msg: dict[str, Any] = {"role": "assistant", "content": m.content or None}
            if m.tool_calls:
                msg["tool_calls"] = [{"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.arguments, ensure_ascii=False)}} for c in m.tool_calls]
            out.append(msg)
        elif m.role == "tool":
            out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content})
        elif m.role == "user":
            out.append({"role": "user", "content": m.content})
    return out


class OpenAICompatibleClient(HTTPProvider):
    name = "openai_compatible"

    def __init__(self, config: LLMConfig, transport: httpx.BaseTransport | None = None, **kw: Any) -> None:
        super().__init__(config, transport, **kw)
        self.url = config.base_url.rstrip("/") + "/chat/completions"

    def complete(self, system: str, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.config.model, "max_tokens": self.config.max_tokens, "temperature": self.config.temperature,
            "messages": to_wire_messages(system, messages),
        }
        if tools:
            body["tools"] = [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}} for t in tools]
        headers = {"content-type": "application/json"}
        if self.config.api_key:
            headers["authorization"] = f"Bearer {self.config.api_key}"
        data = self._post(self.url, headers, body)
        try:
            choice = data["choices"][0]
            msg = choice["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError("openai_compatible : champ 'choices' absent ou vide") from exc
        calls = []
        for c in msg.get("tool_calls") or []:
            try:
                args = json.loads(c["function"]["arguments"] or "{}")
                if not isinstance(args, dict):
                    raise ValueError
                calls.append(ToolCall(str(c["id"]), str(c["function"]["name"]), args))
            except (KeyError, TypeError, ValueError) as exc:
                raise LLMResponseError("openai_compatible : appel d'outil invalide") from exc
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return LLMResponse(str(msg.get("content") or ""), tuple(calls), str(choice.get("finish_reason") or "end"), {k: v for k, v in usage.items() if isinstance(v, int)})
