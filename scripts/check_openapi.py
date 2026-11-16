#!/usr/bin/env python3
"""Verifie docs/contract/openapi-public.yaml (AS-S1-003) : validite OpenAPI + regles du projet.

Usage : python scripts/check_openapi.py        (dependances : pyyaml, openapi-spec-validator)
Code de sortie 0 = conforme.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from openapi_spec_validator import validate

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "contract" / "openapi-public.yaml"
VERDICT = ROOT / "docs" / "contract" / "verdict.schema.json"
ROLES = {"ANALYST", "APPROVER", "ADMIN"}
METHODS = {"get", "post", "put", "patch", "delete"}


def main() -> int:
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    errors: list[str] = []

    try:
        validate(spec)
    except Exception as exc:  # noqa: BLE001 - on veut le message de l'outil
        print(f"Specification OpenAPI invalide : {exc}")
        return 1

    for path, item in spec["paths"].items():
        for method, op in item.items():
            if method not in METHODS:
                continue
            where = f"{method.upper()} {path}"
            roles = op.get("x-roles")
            if not isinstance(roles, list) or not set(roles) <= ROLES:
                errors.append(f"{where} : `x-roles` absent ou invalide (attendu : liste incluse dans {sorted(ROLES)})")
                continue
            responses = op.get("responses", {})
            if roles:  # route protegee
                if op.get("security") == []:
                    errors.append(f"{where} : route avec roles mais `security: []`")
                for code in ("401", "403"):
                    if code not in responses:
                        errors.append(f"{where} : reponse {code} manquante")
            elif op.get("security") != []:
                errors.append(f"{where} : route publique (`x-roles: []`) sans `security: []` explicite")
            if path.endswith(("/approve", "/reject")) and "409" not in responses:
                errors.append(f"{where} : reponse 409 manquante")

    # Le schema Verdict de l'API doit rester identique au contrat partage.
    ref = json.loads(VERDICT.read_text(encoding="utf-8"))
    api = spec["components"]["schemas"]["Verdict"]
    if set(api["properties"]) != set(ref["properties"]):
        errors.append(f"Verdict : proprietes differentes ({sorted(set(api['properties']) ^ set(ref['properties']))})")
    if set(api["required"]) != set(ref["required"]):
        errors.append("Verdict : champs requis differents du schema de reference")
    if api.get("additionalProperties") is not False:
        errors.append("Verdict : `additionalProperties: false` attendu")
    enums = spec["components"]["schemas"]
    for prop, schema_name in (("module", "GuardModule"), ("attackType", "AttackType"), ("riskLevel", "RiskLevel")):
        if set(enums[schema_name]["enum"]) != set(ref["properties"][prop]["enum"]):
            errors.append(f"Verdict.{prop} : valeurs differentes du schema de reference")
    ref_decisions = {v for v in ref["properties"]["decision"]["enum"] if v is not None}
    if set(enums["Decision"]["enum"]) != ref_decisions:
        errors.append("Verdict.decision : valeurs differentes du schema de reference")

    if errors:
        print("Specification non conforme :")
        for e in errors:
            print(f"  - {e}")
        return 1
    n = sum(1 for item in spec["paths"].values() for m in item if m in METHODS)
    print(f"OpenAPI conforme : {len(spec['paths'])} chemins, {n} operations, roles explicites partout.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
