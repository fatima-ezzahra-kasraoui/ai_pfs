"""Attaque « tool abuse » sans protection (AS-S1-028) : `python -m evaluation.attacks.tool_abuse`."""
from __future__ import annotations

from ._common import run_attack

FAMILY = "tool_abuse"

if __name__ == "__main__":
    raise SystemExit(run_attack(FAMILY))
