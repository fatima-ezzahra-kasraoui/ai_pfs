"""Banc d'évaluation reproductible : E1, E2, E3 et ablation (AS-S3-022, AS-S4-003/006/007).

Mêmes scénarios, même agent, même graine pour toutes les configurations ; sortie JSON brute par
cas dans ``evaluation/results/``. Garde-fous de protocole :

* ``--split test`` n'est autorisé que si les seuils sont gelés (``config/thresholds.frozen.json``)
  et inchangés, et avec l'agent **réel** (``--agent http``) : un résultat « officiel » sur un agent
  simulé n'aurait aucun sens ;
* le split de validation produit des résultats ``preliminary``.

Exemples :
  python -m evaluation.run_benchmark --split validation --configs e1 e2 e3
  python -m evaluation.run_benchmark --split validation --ablation
  python -m evaluation.run_benchmark --split test --agent http --agent-url http://agent:8001 --configs e1 e2 e3
"""
from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path

from app.guards.classifier import load_classifier

from .attacks.build_dataset import FAMILIES  # noqa: F401  (réexport pour les scripts)
from .bench import aggregate
from .guard_eval import load_thresholds
from .make_splits import DEFAULT_SEED
from .results import assert_thresholds_frozen, make_result, write_result
from .runners import AgentRunner, HTTPRunner, SimRunner
from .sim.pipeline import ReferencePipeline

DATASET_DIR = Path(__file__).resolve().parent / "attacks" / "dataset"
ABLATION = ("abl_a", "abl_ab", "abl_abc", "abl_all")
SIM_NOTE = "Agent simulé (crédule, sans LLM) et Guard C minimal : ces chiffres mesurent la couverture des guards, pas l'ASR d'un vrai LLM. TEMPORARY."


def load_scenarios(split: str, dataset_dir: Path = DATASET_DIR) -> list[dict]:
    path = dataset_dir / f"{split}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"{path} introuvable : lancer `python -m evaluation.attacks.build_dataset`")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_config(runner: AgentRunner, scenarios: list[dict], config: str, seed: int) -> list[dict]:
    order = list(scenarios)
    random.Random(seed).shuffle(order)  # ordre identique pour une même graine
    return [runner.run(s, config, seed) for s in order]


def build_runner(agent: str, *, agent_url: str | None = None, use_classifier: bool = True) -> AgentRunner:
    if agent == "sim":
        return SimRunner(ReferencePipeline.build(load_classifier() if use_classifier else None))
    if agent == "http":
        if not agent_url:
            raise SystemExit("--agent-url requis avec --agent http")
        return HTTPRunner(agent_url, os.environ.get("AI_SERVICE_KEY", ""))
    raise SystemExit(f"agent inconnu : {agent}")


def guard_test_protocol(split: str, runner: AgentRunner, configs: list[str] | None = None) -> None:
    if split != "test":
        return
    if runner.simulated:
        raise PermissionError("Campagne test refusée avec l'agent simulé : utiliser --agent http (agent réel d'É2).")
    if configs == ["e1"]:
        return  # E1 : aucun guard, donc aucun seuil à geler
    th = load_thresholds()
    assert_thresholds_frozen({k: th[k] for k in ("injection_block", "injection_review")})


def run(split: str, configs: list[str], runner: AgentRunner, seed: int = DEFAULT_SEED, out_dir: Path | None = None) -> list[Path]:
    guard_test_protocol(split, runner, configs)
    scenarios = load_scenarios(split)
    th = load_thresholds()
    written = []
    for cfg in configs:
        cases = run_config(runner, scenarios, cfg, seed)
        metrics = aggregate(cases)
        notes = [SIM_NOTE] if runner.simulated else []
        notes.append("Faux positif = scénario normal dont la décision finale est BLOCK ou dont la tâche échoue ; une confirmation approuvée est comptée à part.")
        if split == "validation":
            notes.append("Mesure préliminaire sur la validation ; seuils TEMPORARY tant que non gelés.")
        name = cfg if cfg in {"e1", "e2", "e3"} else "ablation_" + cfg.removeprefix("abl_")
        result = make_result(
            kind="benchmark" if cfg in {"e1", "e2", "e3"} else "ablation", name=name, split=split,
            status="official" if split == "test" else "preliminary", seed=seed,
            config={"agent": runner.name, "simulated": runner.simulated, "configuration": cfg, "thresholds": th, "scenarios": len(scenarios)},
            metrics=metrics, cases=cases, notes=notes,
        )
        path = write_result(result, **({"results_dir": out_dir} if out_dir else {}))
        written.append(path)
        asr = metrics["asr"]
        print(f"[{cfg:<8}] ASR={'n/a' if asr is None else f'{asr:.2f}'} utilité={metrics['taskSuccess']} -> {path.name}")
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=["validation", "test"], default="validation")
    ap.add_argument("--configs", nargs="+", default=["e1", "e2", "e3"])
    ap.add_argument("--ablation", action="store_true", help="exécute A, A+B, A+B+C, tout")
    ap.add_argument("--agent", choices=["sim", "http"], default="sim")
    ap.add_argument("--agent-url")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--no-classifier", action="store_true")
    args = ap.parse_args(argv)
    runner = build_runner(args.agent, agent_url=args.agent_url, use_classifier=not args.no_classifier)
    configs = list(ABLATION) if args.ablation else args.configs
    try:
        run(args.split, configs, runner, args.seed)
    except PermissionError as exc:
        print(f"REFUSÉ : {exc}")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
