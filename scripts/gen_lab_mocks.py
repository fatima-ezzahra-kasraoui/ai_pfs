#!/usr/bin/env python3
"""Génère frontend/src/mocks/simulation.fixtures.ts à partir d'EXÉCUTIONS RÉELLES de l'agent (AS-S1-024).

Pour chacun des 5 scénarios, l'agent du service IA est exécuté sans puis avec protection (LLM SIMULÉ, outils factices) et le résultat
est converti au format `Simulation` du contrat public (6 étapes). Les fixtures reflètent donc le comportement mesuré de la
version courante, pas des valeurs écrites à la main. Ce sont des DONNÉES DE DÉMONSTRATION (bandeau obligatoire dans le Lab).

Usage : python scripts/gen_lab_mocks.py     (depuis la racine du dépôt ; nécessite les dépendances de ai-service)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai-service"))

from app.agent.service import AgentService, RunInput, demo_catalog  # noqa: E402
from app.api import security  # noqa: E402
from app.llm.providers.mock import SimulatedLLM  # noqa: E402

OUT = ROOT / "frontend" / "src" / "mocks" / "simulation.fixtures.ts"
STEPS = ["Message utilisateur", "Décision de l'agent", "Appel d'outil", "Résultat d'outil", "Moteur de décision", "Réponse finale"]
# scénario du contrat public -> (scénario du catalogue de démonstration, message)
SCENARIOS = {
    "scenario-1": ("demo-1-injection-directe", None),
    "scenario-2": ("demo-2-injection-indirecte", None),
    "scenario-3": ("demo-3-fuite-faux-secret", None),
    "scenario-4": ("demo-4-outil-dangereux", None),
    "scenario-5": (None, "Résume mes mails."),
}
SEVERITY = {"ALLOW": 0, "SANITIZE": 1, "CONFIRM": 2, "BLOCK": 3}


def _strip(verdict: dict) -> dict:
    v = dict(verdict)
    v.pop("latencyMs", None)  # temps mesuré : non reproductible, inutile à l'affichage
    return v


def verdict_for(events, stage):
    """Verdict du pas : celui du guard le plus sévère de l'étape (Verdict réel ; sa décision est celle que le moteur lui a attribuée)."""
    picked = None
    for e in events:
        if e.stage == stage and e.module != "ENGINE" and e.verdict is not None and (picked is None or SEVERITY[e.decision] > SEVERITY[picked.decision]):
            picked = e
    if picked is None:
        return None
    v = _strip(picked.verdict)
    v["decision"] = picked.decision  # décision du moteur pour la contribution de ce guard (le Verdict du guard porte decision = null)
    return v


def engine_verdict(events):
    """Verdict ENGINE le plus sévère de l'exécution (étape « Moteur de décision »)."""
    picked = None
    for e in events:
        if e.module == "ENGINE" and e.verdict is not None and (picked is None or SEVERITY[e.decision] > SEVERITY[picked.decision]):
            picked = e
    return _strip(picked.verdict) if picked else None


def to_run(mode, outcome, attack_expected):
    protected = mode == "protected"
    ev = outcome.events
    blocked = outcome.halted == "input_blocked"
    attempted = bool(outcome.executed) or any(e.stage == "tool_call" for e in ev)  # un appel d'outil a été demandé
    returned = bool(outcome.executed)  # l'outil a réellement été exécuté (simulé) : il a renvoyé un résultat
    steps = []
    for i, name in enumerate(STEPS):
        stage = {0: "input", 2: "tool_call", 3: "tool_content", 5: "final_response"}.get(i)
        if i == 4:  # moteur de décision : il a décidé à chaque étape contrôlée (absent sans protection)
            v = engine_verdict(ev) if protected else None
            status = "DONE" if v else "SKIPPED"
        elif i == 1:
            status, v = ("SKIPPED" if blocked else "DONE"), None
        elif i in (2, 3):
            status, v = ("DONE" if (attempted if i == 2 else returned) else "SKIPPED"), (verdict_for(ev, stage) if protected else None)
        else:  # étapes de garde (message, réponse finale)
            if protected and not (blocked and i == 5):
                status, v = "DONE", verdict_for(ev, stage)
            else:
                status, v = "SKIPPED", None
        steps.append({"name": name, "status": status, "verdict": v})
    attack = outcome.attack_succeeded if attack_expected else False
    return {"mode": mode, "steps": steps, "finalDecision": outcome.final_decision if protected else None, "attackSucceeded": bool(attack), "finalResponse": outcome.final_text}


def render() -> str:
    """Contenu complet du fichier de fixtures (déterministe : LLM simulé, graine fixe)."""
    # Deterministic demo fixtures, independent of optional local ML models.
    from unittest.mock import patch

    with patch("app.guards.classifier.load_classifier", return_value=None), patch(
        "app.guards.output_guard.try_load_presidio", return_value=None
    ):
        guards = security.build_guards()

    svc = AgentService(SimulatedLLM(), guards)
    catalog = demo_catalog()
    fixtures = {}
    for sid, (demo, message) in SCENARIOS.items():
        s = catalog[demo] if demo else None
        base = dict(message=s["user_message"] if s else message, scenario_id=demo, tool_fixture=s["tool"] if s else None, confirmation_policy="auto", seed=42, correlation_id=f"mock-{sid}")
        runs = {m: svc.run(RunInput(config="e1" if m == "unprotected" else "e3", **base)) for m in ("unprotected", "protected")}
        fixtures[sid] = {m: to_run(m, o, attack_expected=s is not None) for m, o in runs.items()}
    body = json.dumps(fixtures, ensure_ascii=False, indent=2)
    return (
        "// FICHIER GÉNÉRÉ par scripts/gen_lab_mocks.py à partir d'exécutions réelles de l'agent (LLM simulé, outils factices).\n"
        "// DONNÉES DE DÉMONSTRATION (TEMPORARY) : ne pas modifier à la main ; supprimé avec le mock (AS-S2-031).\n"
        'import type { SimulationRun } from "../services/simulation.service";\n\n'
        "export const SIMULATION_FIXTURES: Record<string, { unprotected: SimulationRun; protected: SimulationRun }> = " + body + " as never;\n"
    )


def main() -> int:
    OUT.write_text(render(), encoding="utf-8")
    fixtures = json.loads(OUT.read_text(encoding="utf-8").split("= ", 1)[1].rsplit(" as never", 1)[0])
    print(f"{OUT.relative_to(ROOT)} : {len(fixtures)} scénarios")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
