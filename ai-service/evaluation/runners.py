"""Exécuteurs de scénarios : simulation locale et agent réel (AS-S3-022, AS-S1-028).

Interface unique ``AgentRunner.run(scenario, config) -> dict`` pour que le même banc rejoue :

* ``SimRunner``  : pipeline de référence sans LLM (TEMPORARY, voir ``sim.pipeline``) ;
* ``HTTPRunner`` : agent réel d'É2 via ``POST /internal/agent/run``.

Le contrat HTTP ci-dessous est **à confirmer avec É2** (AS-S1-022) ; il est isolé ici pour qu'un
changement ne touche que ce fichier.
"""
from __future__ import annotations

from typing import Any, Protocol

import httpx

from .sim.pipeline import CONFIGS, E2, ReferencePipeline

ALL_CONFIGS = ("e1", E2, "e3", "abl_a", "abl_ab", "abl_abc", "abl_all")
MODE_FOR = {"e1": "unprotected"}  # toute autre configuration : « protected »


class AgentRunner(Protocol):
    name: str
    simulated: bool

    def run(self, scenario: dict[str, Any], config: str, seed: int) -> dict[str, Any]: ...


class SimRunner:
    name = "simulated_gullible"
    simulated = True

    def __init__(self, pipeline: ReferencePipeline) -> None:
        self.pipeline = pipeline

    def run(self, scenario: dict[str, Any], config: str, seed: int) -> dict[str, Any]:
        if config != E2 and config not in CONFIGS:
            raise ValueError(f"configuration inconnue : {config}")
        return self.pipeline.run(scenario, config).to_dict()


class HTTPRunner:
    name = "http_agent"
    simulated = False

    def __init__(self, base_url: str, service_key: str, client: httpx.Client | None = None, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=timeout)
        self.headers = {"X-AI-Service-Key": service_key}

    def run(self, scenario: dict[str, Any], config: str, seed: int) -> dict[str, Any]:
        body = {
            "scenarioId": scenario["id"], "message": scenario["user_message"], "toolFixture": scenario.get("tool"),
            "mode": MODE_FOR.get(config, "protected"), "config": config, "seed": seed,
        }
        r = self.client.post(f"{self.base_url}/internal/agent/run", json=body, headers=self.headers)
        r.raise_for_status()
        data = r.json()
        steps = [{"stage": e.get("stage", ""), "module": e["module"], "decision": e["decision"], "score": e.get("score"), "reason": e.get("reason", ""), "latencyMs": e.get("latencyMs", 0.0)} for e in data.get("events", [])]
        is_attack = scenario["family"] != "normal"
        return {
            "id": scenario["id"], "family": scenario["family"], "config": config,
            "attackSucceeded": bool(data["attackSucceeded"]) if is_attack else None,
            "taskSucceeded": (None if is_attack else bool(data.get("taskSucceeded"))),
            "finalDecision": data.get("finalDecision", "ALLOW"), "confirmations": int(data.get("confirmations", 0)),
            "detected": any(s["decision"] != "ALLOW" for s in steps), "totalMs": float(data.get("totalMs", 0.0)), "steps": steps, "executed": [],
        }
