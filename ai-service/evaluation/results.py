"""Écriture et lecture des fichiers de résultats (AS-S3-020).

Règle d'or : aucun chiffre saisi à la main. Un fichier de résultats est produit par un
script, horodaté et rattaché au commit Git ; ``status`` distingue les mesures
``preliminary`` (validation) des mesures ``official`` (campagne test, seuils gelés).
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

RESULTS_DIR = Path(__file__).resolve().parent / "results"
SCHEMA_PATH = Path(__file__).resolve().parent / "results.schema.json"
FROZEN_PATH = Path(__file__).resolve().parents[1] / "config" / "thresholds.frozen.json"
KINDS = ("detection", "benchmark", "ablation", "threshold_tuning", "attack_run")


def git_state() -> tuple[str, bool]:
    """(commit, dirty). Hors dépôt Git : (« unknown », True)."""
    cwd = Path(__file__).resolve().parent
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip())
        return commit, dirty
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown", True


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_result(data: dict) -> None:
    jsonschema.validate(data, load_schema())


def make_result(
    *,
    kind: str,
    name: str,
    split: str,
    status: str,
    seed: int,
    config: dict[str, Any],
    metrics: dict[str, Any],
    cases: list[dict[str, Any]] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    commit, dirty = git_state()
    data: dict[str, Any] = {
        "schemaVersion": 1,
        "kind": kind,
        "name": name,
        "split": split,
        "status": status,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": commit,
        "dirty": dirty,
        "seed": seed,
        "config": config,
        "metrics": metrics,
    }
    if cases is not None:
        data["cases"] = cases
    if notes:
        data["notes"] = notes
    return data


def write_result(data: dict[str, Any], results_dir: Path = RESULTS_DIR) -> Path:
    validate_result(data)
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = data["generatedAt"].replace(":", "").replace("-", "").replace("+0000", "Z").split("+")[0]
    path = results_dir / f"{data['name']}_{data['split']}_{stamp}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_results(results_dir: Path = RESULTS_DIR) -> list[dict[str, Any]]:
    """Lit tous les fichiers valides ; un fichier invalide est refusé (jamais ignoré en silence)."""
    out: list[dict[str, Any]] = []
    for path in sorted(results_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        validate_result(data)
        data["_file"] = path.name
        out.append(data)
    return out


# --------------------------------------------------------------------- gel des seuils
def load_frozen() -> dict[str, Any] | None:
    if not FROZEN_PATH.exists():
        return None
    return json.loads(FROZEN_PATH.read_text(encoding="utf-8"))


def assert_thresholds_frozen(current: dict[str, float]) -> None:
    """Refuse la campagne officielle sur le test si les seuils ne sont pas gelés ou ont changé."""
    frozen = load_frozen()
    if frozen is None:
        raise PermissionError("Seuils non gelés : lancer `python -m evaluation.tune_thresholds --freeze` avant toute mesure sur le test.")
    if {k: frozen["thresholds"].get(k) for k in current} != current:
        raise PermissionError("Les seuils de policy.yaml ont changé depuis le gel (thresholds.frozen.json) : mesure sur le test refusée.")
