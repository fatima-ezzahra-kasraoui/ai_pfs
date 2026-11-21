#!/usr/bin/env python3
"""Valide docs/contract/openapi-internal.yaml (OpenAPI 3.1) et sa synchronisation avec verdict.schema.json.

Usage : python scripts/validate_openapi.py   (nécessite pyyaml et openapi-spec-validator)
La conformité complète avec l'implémentation FastAPI est vérifiée par ai-service/tests/test_openapi_contract.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from openapi_spec_validator import validate

CONTRACT = Path(__file__).resolve().parents[1] / "docs" / "contract"


def main() -> int:
    spec = yaml.safe_load((CONTRACT / "openapi-internal.yaml").read_text(encoding="utf-8"))
    validate(spec)
    verdict = json.loads((CONTRACT / "verdict.schema.json").read_text(encoding="utf-8"))
    component = spec["components"]["schemas"]["Verdict"]
    if component["properties"] != verdict["properties"] or component["required"] != verdict["required"]:
        print("ERREUR : le composant Verdict de l'OpenAPI diffère de verdict.schema.json", file=sys.stderr)
        return 1
    operations = sum(1 for item in spec["paths"].values() for m in item if m in {"get", "post", "put", "patch", "delete"})
    print(f"OpenAPI valide : {operations} opérations, composant Verdict synchronisé.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
