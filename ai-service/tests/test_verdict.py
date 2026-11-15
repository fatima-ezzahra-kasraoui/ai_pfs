import json
from pathlib import Path

import jsonschema
import pytest

from app.models.verdict import Verdict, risk_from_score

SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "docs/contract/verdict.schema.json").read_text())


def make(**kw):
    base = dict(module="A", score=0.5, attack_type="none", reason="r")
    base.update(kw)
    return Verdict(**base)


def test_valid_verdict_matches_schema():
    v = make(score=0.92, attack_type="direct_injection", risk_level="high", correlation_id="abc")
    jsonschema.validate(v.to_dict(), SCHEMA)


@pytest.mark.parametrize("bad", [-0.01, 1.01, 5])
def test_score_out_of_range_rejected(bad):
    with pytest.raises(ValueError):
        make(score=bad)


def test_unknown_module_rejected():
    with pytest.raises(ValueError):
        make(module="Z")


def test_unknown_attack_type_rejected():
    with pytest.raises(ValueError):
        make(attack_type="magic")


def test_bool_score_rejected():
    with pytest.raises(ValueError):
        make(score=True)


def test_invalid_decision_rejected():
    with pytest.raises(ValueError):
        make(decision="MAYBE")


def test_schema_rejects_out_of_range_score():
    data = make().to_dict()
    data["score"] = 1.5
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, SCHEMA)


def test_guard_never_sets_decision_by_default():
    assert make().decision is None


@pytest.mark.parametrize("score,level", [(0.0, "low"), (0.49, "low"), (0.5, "medium"), (0.89, "medium"), (0.9, "high")])
def test_risk_from_score(score, level):
    assert risk_from_score(score).value == level
