"""Attaque « indirect injection » sans protection (AS-S1-028) : `python -m evaluation.attacks.indirect_injection`."""
from __future__ import annotations

from ._common import run_attack

FAMILY = "indirect_injection"

if __name__ == "__main__":
    raise SystemExit(run_attack(FAMILY))
