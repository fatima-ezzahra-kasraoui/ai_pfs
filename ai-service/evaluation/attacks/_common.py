"""Briques communes des scripts d'attaque sans protection (AS-S1-028)."""
from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.bench import aggregate
from evaluation.make_splits import DEFAULT_SEED
from evaluation.results import RESULTS_DIR, make_result, write_result
from evaluation.run_benchmark import build_runner, guard_test_protocol, load_scenarios, run_config

EXPECTED = (
    "Résultat attendu en E1 (agent sans protection) : l'attaque réussit (attackSucceeded = true) pour tous les "
    "scénarios de la famille. Si un scénario échoue en E1, c'est un défaut du scénario ou de l'agent, à corriger "
    "avant toute comparaison avec E2 / E3."
)


def run_attack(family: str, argv: list[str] | None = None, out_dir: Path = RESULTS_DIR) -> int:
    ap = argparse.ArgumentParser(description=f"Rejoue les scénarios « {family} » sans protection (config E1).")
    ap.add_argument("--split", choices=["validation", "test"], default="validation")
    ap.add_argument("--agent", choices=["sim", "http"], default="sim")
    ap.add_argument("--agent-url")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args(argv)
    runner = build_runner(args.agent, agent_url=args.agent_url, use_classifier=False)
    try:
        guard_test_protocol(args.split, runner, ["e1"])
    except PermissionError as exc:
        print(f"REFUSÉ : {exc}")
        return 3
    scenarios = [s for s in load_scenarios(args.split) if s["family"] == family]
    cases = run_config(runner, scenarios, "e1", args.seed)
    metrics = aggregate(cases)
    fam = metrics["perFamily"][family]
    result = make_result(
        kind="attack_run", name=f"attack_{family}", split=args.split, status="official" if args.split == "test" else "preliminary", seed=args.seed,
        config={"family": family, "agent": runner.name, "simulated": runner.simulated, "configuration": "e1", "scenarios": len(scenarios)},
        metrics={"attempted": fam["attempted"], "succeeded": fam["succeeded"], "asr": fam["asr"]}, cases=cases,
        notes=[EXPECTED] + (["Agent simulé (crédule) : ce taux est vrai par construction. TEMPORARY."] if runner.simulated else []),
    )
    path = write_result(result, out_dir)
    print(f"{family}: {fam['succeeded']}/{fam['attempted']} attaques réussies sans protection (agent {runner.name}) -> {path.name}")
    return 0
