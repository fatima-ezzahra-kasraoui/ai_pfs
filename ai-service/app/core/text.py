"""Utilitaires de texte partagés par les guards : normalisation Unicode et découpage."""
from __future__ import annotations

import re
import unicodedata

# Caractères invisibles ou de contrôle de direction souvent utilisés pour cacher une instruction.
INVISIBLE_CHARS = {
    "​", "‌", "‍", "⁠", "﻿", "­",
    "‎", "‏", "‪", "‫", "‬", "‭", "‮",
    "⁦", "⁧", "⁨", "⁩",
}

# Homoglyphes courants (cyrillique / grec -> latin) utilisés pour contourner des mots-clés.
HOMOGLYPHS = str.maketrans(
    {
        "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
        "і": "i", "ј": "j", "ѕ": "s", "ԁ": "d", "ɡ": "g", "һ": "h", "ո": "n",
        "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K",
        "Μ": "M", "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Χ": "X", "Υ": "Y",
        "ο": "o", "ν": "v", "ι": "i",
        "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O",
        "Р": "P", "С": "C", "Т": "T", "Х": "X",
    }
)

_WS = re.compile(r"\s+")


def strip_invisible(text: str) -> tuple[str, int]:
    """Supprime les caractères invisibles ; retourne (texte, nombre retiré)."""
    removed = sum(1 for c in text if c in INVISIBLE_CHARS)
    if not removed:
        return text, 0
    return "".join(c for c in text if c not in INVISIBLE_CHARS), removed


def normalize(text: str) -> tuple[str, dict[str, int]]:
    """Normalise un texte avant détection.

    Étapes : NFKC, suppression des caractères invisibles, remplacement des
    homoglyphes courants, réduction des espaces. Retourne le texte normalisé et
    des statistiques (``invisible``, ``homoglyphs``) utiles comme signal d'évasion.
    """
    text = unicodedata.normalize("NFKC", text or "")
    text, invisible = strip_invisible(text)
    translated = text.translate(HOMOGLYPHS)
    homoglyphs = sum(1 for a, b in zip(text, translated, strict=True) if a != b)
    translated = _WS.sub(" ", translated).strip()
    return translated, {"invisible": invisible, "homoglyphs": homoglyphs}


def fold(text: str) -> str:
    """Minuscule sans accents, pour les comparaisons de motifs FR/EN."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    """Découpe un long texte en morceaux avec recouvrement (scan par chunks).

    Le recouvrement évite qu'une instruction à cheval sur deux morceaux échappe à
    la détection. Un texte court ou vide donne au plus un morceau.
    """
    if max_chars <= overlap:
        raise ValueError("max_chars doit être supérieur à overlap")
    text = text or ""
    if len(text) <= max_chars:
        return [text] if text else []
    chunks: list[str] = []
    start = 0
    step = max_chars - overlap
    while start < len(text):
        chunks.append(text[start : start + max_chars])
        if start + max_chars >= len(text):
            break
        start += step
    return chunks


_SPACED = re.compile(r"(?<!\S)(?:\S ){2,}\S(?!\S)")


def despace(text: str) -> str:
    """Recolle les mots écrits lettre par lettre (« i g n o r e »), signal d'évasion courant.

    Les mots sont séparés par au moins deux espaces dans le texte brut ; sans cela, la suite de
    lettres isolées est recollée en un seul bloc.
    """
    pieces = re.split(r" {2,}", text or "")
    fixed = [_SPACED.sub(lambda m: m.group(0).replace(" ", ""), piece) for piece in pieces]
    return " ".join(fixed)
