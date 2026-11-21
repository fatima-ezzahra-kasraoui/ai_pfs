"""Socle HTTP commun : délais, nouvelles tentatives bornées, traduction des erreurs."""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from ..config import LLMConfig
from ..errors import LLMProviderError, LLMResponseError, LLMTimeoutError

log = logging.getLogger("agentshield.llm")
RETRYABLE = {408, 429, 500, 502, 503, 504}


class HTTPProvider:
    simulated = False
    name = "http"

    def __init__(self, config: LLMConfig, transport: httpx.BaseTransport | None = None, sleep: Callable[[float], None] = time.sleep) -> None:
        self.config = config
        self._http = httpx.Client(timeout=config.timeout_s, transport=transport)
        self._sleep = sleep

    def _post(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        attempts = self.config.max_retries + 1
        for attempt in range(attempts):
            last = attempt == attempts - 1
            try:
                r = self._http.post(url, headers=headers, json=body)
            except httpx.TimeoutException as exc:
                if last:
                    raise LLMTimeoutError(f"{self.name} : délai dépassé ({self.config.timeout_s:g} s)") from exc
            except httpx.HTTPError as exc:
                if last:
                    raise LLMProviderError(f"{self.name} : erreur réseau ({type(exc).__name__})") from exc
            else:
                if r.status_code < 400:
                    try:
                        data = r.json()
                    except ValueError as exc:
                        raise LLMResponseError(f"{self.name} : réponse non JSON") from exc
                    if not isinstance(data, dict):
                        raise LLMResponseError(f"{self.name} : réponse JSON inattendue")
                    return data
                if r.status_code not in RETRYABLE or last:
                    # Ni le corps ni les en-têtes ne sont repris : ils pourraient contenir des données sensibles.
                    raise LLMProviderError(f"{self.name} : HTTP {r.status_code}", status=r.status_code)
            log.warning("llm retry provider=%s attempt=%d", self.name, attempt + 1)
            self._sleep(0.5 * (2**attempt))
        raise LLMProviderError(f"{self.name} : échec")  # pragma: no cover - boucle toujours terminée par un raise/return
