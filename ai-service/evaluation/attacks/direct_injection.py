"""Attaque « direct injection » sans protection (AS-S1-028) : `python -m evaluation.attacks.direct_injection`."""
from __future__ import annotations

from ._common import run_attack

FAMILY = "direct_injection"

if __name__ == "__main__":
    raise SystemExit(run_attack(FAMILY))
