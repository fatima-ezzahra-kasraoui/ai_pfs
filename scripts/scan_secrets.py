#!/usr/bin/env python3
"""Scan des secrets dans le dépôt (AS-S3-024, NF01).

Détecte des motifs de clés réelles. Le canary factice ``sk-FAKE-1234`` est
explicitement autorisé : c'est une donnée de test, pas un secret.
Utilisation : ``python scripts/scan_secrets.py [chemin ...]`` (code 1 si secret).
Hook pré-push : ``cp scripts/pre-push.sample .git/hooks/pre-push``.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_SUBSTRINGS = ("sk-FAKE-1234",)
SKIP_DIRS = {".git", "node_modules", "dist", ".venv", "venv", "__pycache__"}
SKIP_FILES = {"scan_secrets.py", "test_scan_secrets.py"}

PATTERNS: dict[str, re.Pattern[str]] = {
    "clé API sk-": re.compile(r"\bsk-(?!FAKE)[A-Za-z0-9]{20,}\b"),
    "clé AWS": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "jeton GitHub": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "clé privée": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "mot de passe en dur": re.compile(
        r"(?i)\b(?:password|passwd|secret)\b\s*[:=]\s*['\"](?!change-me|<|\$\{)[^'\"\s]{8,}['\"]"
    ),
}


def scan_text(text: str) -> list[tuple[str, str]]:
    """Retourne la liste (type, extrait masqué) des secrets trouvés dans ``text``."""
    findings: list[tuple[str, str]] = []
    for line in text.splitlines():
        if any(ok in line for ok in ALLOWED_SUBSTRINGS):
            line = line.replace("sk-FAKE-1234", "")
        for name, pattern in PATTERNS.items():
            match = pattern.search(line)
            if match:
                findings.append((name, match.group(0)[:4] + "****"))
    return findings


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.split()
        paths = [ROOT / p for p in out]
    except (subprocess.CalledProcessError, FileNotFoundError):
        paths = [p for p in ROOT.rglob("*") if p.is_file()]
    return [
        p
        for p in paths
        if p.is_file()
        and p.name not in SKIP_FILES
        and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS)
    ]


def main(argv: list[str]) -> int:
    files = [Path(a) for a in argv] if argv else tracked_files()
    failed = False
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for kind, excerpt in scan_text(text):
            failed = True
            print(f"SECRET ({kind}) dans {path}: {excerpt}")
    if failed:
        print("Échec : retirer les secrets puis les faire tourner (rotation).")
        return 1
    print("Aucun secret détecté.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
