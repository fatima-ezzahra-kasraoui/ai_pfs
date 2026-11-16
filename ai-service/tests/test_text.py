import pytest

from app.core.text import chunk_text, fold, normalize, strip_invisible


def test_strip_invisible_counts():
    text, n = strip_invisible("ig​no‍re")
    assert text == "ignore" and n == 2


def test_normalize_homoglyphs_and_stats():
    # « о » cyrillique à la place du « o » latin
    out, stats = normalize("ignоre")
    assert out == "ignore" and stats["homoglyphs"] == 1


def test_normalize_collapses_whitespace_and_nfkc():
    out, _ = normalize("  ｉｇｎｏｒｅ \n  tout ")
    assert out == "ignore tout"


def test_fold_removes_accents():
    assert fold("Révèle MA clé") == "revele ma cle"


def test_chunk_short_and_empty():
    assert chunk_text("") == []
    assert chunk_text("abc") == ["abc"]


def test_chunk_long_with_overlap_covers_all():
    text = "".join(chr(97 + i % 26) for i in range(3000))
    chunks = chunk_text(text, 1000, 100)
    assert len(chunks) > 1
    assert all(len(c) <= 1000 for c in chunks)
    assert chunks[0][-100:] == chunks[1][:100]
    assert chunks[-1].endswith(text[-50:])


def test_chunk_invalid_params():
    with pytest.raises(ValueError):
        chunk_text("x" * 10, 100, 100)
