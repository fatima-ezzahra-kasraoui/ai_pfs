"""Attaque « data leak » sans protection (AS-S1-028) : `python -m evaluation.attacks.data_leak`."""
from __future__ import annotations

from ._common import run_attack

FAMILY = "data_leak"

if __name__ == "__main__":
    raise SystemExit(run_attack(FAMILY))
