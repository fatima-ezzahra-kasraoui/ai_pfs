"""Cache de réponses LLM (AS-S1-022 : « trajectoires avec LLM en cache ») pour des exécutions reproductibles.

``CachedLLM(inner, path)`` enregistre chaque réponse du LLM réel dans un fichier JSON, indexée par l'empreinte de la requête
(système, messages, outils) ; une requête déjà vue est rejouée sans appel. ``offline=True`` interdit tout appel à ``inner`` :
une requête absente du cache lève ``LLMResponseError`` (exécutions sans réseau). Le cache ne contient ni clé ni en-tête.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from .errors import LLMResponseError
from .types import LLMResponse, Message, ToolCall, ToolSpec


def request_key(system: str, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> str:
    payload = {"system": system, "messages": [asdict(m) for m in messages], "tools": [asdict(t) for t in tools]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


class CachedLLM:
    def __init__(self, inner, path: str | Path, offline: bool = False) -> None:
        self.inner, self.path, self.offline = inner, Path(path), offline
        self.name, self.simulated = f"cached:{inner.name}", inner.simulated
        self._lock = threading.Lock()
        self._store: dict[str, dict] = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        self.hits = self.misses = 0

    def complete(self, system: str, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()) -> LLMResponse:
        key = request_key(system, messages, tools)
        with self._lock:
            entry = self._store.get(key)
        if entry is not None:
            self.hits += 1
            return LLMResponse(entry["text"], tuple(ToolCall(c["id"], c["name"], c["arguments"]) for c in entry["tool_calls"]), entry["stop_reason"], entry.get("usage", {}))
        if self.offline:
            raise LLMResponseError("requête absente du cache en mode hors ligne")
        self.misses += 1
        resp = self.inner.complete(system, messages, tools)
        with self._lock:
            self._store[key] = {"text": resp.text, "tool_calls": [asdict(c) for c in resp.tool_calls], "stop_reason": resp.stop_reason, "usage": resp.usage}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._store, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        return resp
