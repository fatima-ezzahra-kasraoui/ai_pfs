import json

import pytest

from app.guards.output_guard import Finding, OutputGuard, iban_valid, luhn_valid, mask_value

VALID_CARD = "4111 1111 1111 1111"  # numéro de test public (Visa)
VALID_IBAN = "FR1420041010050500013M02606"  # IBAN d'exemple public


@pytest.fixture
def guard():
    return OutputGuard()


def test_luhn_and_iban_validators():
    assert luhn_valid("4111111111111111") and not luhn_valid("4111111111111112")
    assert iban_valid(VALID_IBAN) and iban_valid("GB82 WEST 1234 5698 7654 32")
    assert not iban_valid("FR1420041010050500013M02607")


def test_fake_secret_masked_and_flagged_as_canary(guard):
    v = guard.check({"text": "Voici la clé : API_KEY=sk-FAKE-1234. Bonne journée."})
    assert "sk-FAKE-1234" not in v.cleaned
    assert "sk-****" in v.cleaned
    assert v.metadata["canary"] is True and v.score == 1.0
    assert v.attack_type == "data_leak"


def test_raw_secret_never_in_verdict(guard):
    v = guard.check({"text": "API_KEY=sk-FAKE-1234 et carte 4111 1111 1111 1111"})
    dumped = json.dumps(v.to_dict(), ensure_ascii=False)
    assert "sk-FAKE-1234" not in dumped
    assert "4111 1111 1111 1111" not in dumped
    assert "4111111111111111" not in dumped


def test_card_with_valid_luhn_masked_invalid_not(guard):
    v = guard.check({"text": f"carte {VALID_CARD}"})
    assert "**** **** **** 1111" in v.cleaned and "kinds" in v.metadata and "credit_card" in v.metadata["kinds"]
    v2 = guard.check({"text": "référence 4111 1111 1111 1112"})
    assert "credit_card" not in v2.metadata["kinds"]


def test_iban_masked_partially(guard):
    v = guard.check({"text": f"IBAN {VALID_IBAN}"})
    assert "FR14****" in v.cleaned and VALID_IBAN not in v.cleaned


@pytest.mark.parametrize(
    "text",
    [
        "Le total est de 1 234 567,89 MAD.",
        "Commande n° 20260115 livrée le 15/01/2026.",
        "Appelez le service au poste 4521.",
        "La version 3.10.4 est sortie, build 20260101.",
        "Année 2026, 12 345 utilisateurs, 98,6 % de réussite.",
    ],
)
def test_ordinary_numbers_not_masked(guard, text):
    v = guard.check({"text": text})
    assert v.score == 0.0 and v.cleaned == text and v.attack_type == "none"


def test_email_and_french_phone_masked(guard):
    v = guard.check({"text": "Contactez alice.martin@exemple.test ou le 06 12 34 56 78 ou +33 6 12 34 56 78."})
    assert "alice.martin@exemple.test" not in v.cleaned
    assert "a***@exemple.test" in v.cleaned
    assert "06 12 34 56 78" not in v.cleaned and "+33 6 12 34 56 78" not in v.cleaned
    assert {"email", "phone"} <= set(v.metadata["kinds"])


def test_key_value_secret_masked(guard):
    v = guard.check({"text": "password: Sup3rS3cretValue"})
    assert "Sup3rS3cretValue" not in v.cleaned and "Sup****" in v.cleaned


def test_known_token_formats(guard):
    text = "AKIAABCDEFGHIJKLMNOP et ghp_" + "a" * 36
    v = guard.check({"text": text})
    assert v.cleaned.count("****") == 2


def test_canary_in_tool_arguments(guard):
    v = guard.check({"arguments": {"to": "x@exemple.test", "body": "la clé est sk-FAKE-1234"}, "channel": "tool_arguments"})
    assert v.metadata["canary"] is True and v.metadata["channel"] == "tool_arguments"


def test_clean_text_unchanged_and_degraded_flagged(guard):
    v = guard.check({"text": "Tout est en ordre."})
    assert v.cleaned == "Tout est en ordre." and v.degraded is True and v.score == 0.0


def test_person_detector_plugged_in():
    class Fake:
        def detect(self, text):
            i = text.find("Jean Dupont")
            return [Finding("person", i, i + 11)] if i >= 0 else []

    g = OutputGuard(person_detector=Fake())
    v = g.check({"text": "Bonjour Jean Dupont !"})
    assert "[PERSONNE]" in v.cleaned and v.degraded is False


def test_overlap_prefers_canary_over_key_value(guard):
    v = guard.check({"text": "API_KEY=sk-FAKE-1234"})
    assert v.cleaned == "API_KEY=sk-****"
    assert v.metadata["kinds"] == ["canary"]


def test_from_policy_reads_canaries(tmp_path):
    p = tmp_path / "policy.yaml"
    p.write_text("output:\n  canary_tokens: [CANARY-XYZ]\n", encoding="utf-8")
    g = OutputGuard.from_policy(p)
    assert g.check({"text": "voici CANARY-XYZ"}).metadata["canary"] is True


def test_mask_value_unknown_kind():
    assert mask_value("inconnu", "abc") == "****"


def test_no_decision_returned(guard):
    assert guard.check({"text": "sk-FAKE-1234"}).decision is None
