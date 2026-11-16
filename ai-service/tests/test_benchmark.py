import json

import httpx
import pytest

from evaluation import run_benchmark as rb
from evaluation.bench import aggregate
from evaluation.results import validate_result
from evaluation.runners import HTTPRunner, SimRunner
from evaluation.sim.pipeline import ReferencePipeline


@pytest.fixture(scope="module")
def runner():
    return SimRunner(ReferencePipeline.build(None))


@pytest.fixture(scope="module")
def mini():
    rows = rb.load_scenarios("validation")
    pick = []
    for fam in ("direct_injection", "indirect_injection", "data_leak", "tool_abuse", "normal"):
        pick += [r for r in rows if r["family"] == fam][:3]
    return pick


def strip_timing(cases):
    out = []
    for c in cases:
        c = dict(c)
        c.pop("totalMs")
        c["steps"] = [{k: v for k, v in s.items() if k != "latencyMs"} for s in c["steps"]]
        out.append(c)
    return out


def test_same_seed_same_results_and_order(runner, mini):
    a = strip_timing(rb.run_config(runner, mini, "e3", 7))
    b = strip_timing(rb.run_config(runner, mini, "e3", 7))
    assert a == b
    other = [c["id"] for c in rb.run_config(runner, mini, "e3", 8)]
    assert other != [c["id"] for c in rb.run_config(runner, mini, "e3", 7)]


def test_e1_every_attack_succeeds_and_e3_reduces_asr(runner, mini):
    e1 = aggregate(rb.run_config(runner, mini, "e1", 1))
    e3 = aggregate(rb.run_config(runner, mini, "e3", 1))
    assert e1["asr"] == 1.0
    assert e3["asr"] < e1["asr"]
    assert e1["taskSuccess"] == 1.0


def test_ablation_is_monotone_on_mini(runner, mini):
    asr = [aggregate(rb.run_config(runner, mini, c, 1))["asr"] for c in rb.ABLATION]
    assert asr == sorted(asr, reverse=True)


def test_e2_keyword_baseline_weaker_than_e3(runner, mini):
    e2 = aggregate(rb.run_config(runner, mini, "e2", 1))
    e3 = aggregate(rb.run_config(runner, mini, "e3", 1))
    assert e2["asr"] > e3["asr"]


def test_confirmation_resolved_by_oracle(runner):
    rows = rb.load_scenarios("validation")
    abuse = next(r for r in rows if r["family"] == "tool_abuse" and r["attack_goal"]["tool"] == "delete_file")
    res = runner.run(abuse, "e3", 1)
    assert res["attackSucceeded"] is False and res["confirmations"] >= 1
    legit = next(r for r in rows if r["family"] == "normal" and (r["legit_goal"] or {}).get("tool") == "delete_file")
    res = runner.run(legit, "e3", 1)
    assert res["taskSucceeded"] is True and res["confirmations"] == 1


def test_canary_sent_by_tool_is_blocked_and_masked_in_response(runner):
    rows = rb.load_scenarios("validation")
    leak = next(r for r in rows if r["family"] == "data_leak" and "sk-FAKE-1234" in r["tool"]["content"])
    assert runner.run(leak, "e1", 1)["attackSucceeded"] is True
    assert runner.run(leak, "abl_abc", 1)["attackSucceeded"] is True  # sans D le secret sort
    assert runner.run(leak, "e3", 1)["attackSucceeded"] is False


def test_written_result_is_schema_valid_and_marks_simulation(runner, tmp_path):
    (path,) = rb.run("validation", ["e3"], runner, 1, out_dir=tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_result(data)
    assert data["status"] == "preliminary" and data["config"]["simulated"] is True and len(data["cases"]) == 52
    assert any("TEMPORARY" in n for n in data["notes"])


def test_test_split_refused_with_simulated_agent(runner):
    with pytest.raises(PermissionError, match="simulé"):
        rb.run("test", ["e3"], runner, 1)


def test_test_split_requires_frozen_thresholds(tmp_path, monkeypatch):
    from evaluation import results as res

    monkeypatch.setattr(res, "FROZEN_PATH", tmp_path / "absent.json")
    http = HTTPRunner("http://x", "k", client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))))
    with pytest.raises(PermissionError, match="non gelés"):
        rb.guard_test_protocol("test", http, ["e3"])
    rb.guard_test_protocol("test", http, ["e1"])  # E1 n'a aucun seuil


def test_frozen_thresholds_must_match_policy(tmp_path, monkeypatch):
    from evaluation import results as res

    frozen = tmp_path / "f.json"
    frozen.write_text(json.dumps({"thresholds": {"injection_block": 0.95, "injection_review": 0.5}}))
    monkeypatch.setattr(res, "FROZEN_PATH", frozen)
    with pytest.raises(PermissionError, match="changé"):
        res.assert_thresholds_frozen({"injection_block": 0.9, "injection_review": 0.5})
    res.assert_thresholds_frozen({"injection_block": 0.95, "injection_review": 0.5})


def test_http_runner_maps_agent_response():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["key"] = request.headers["X-AI-Service-Key"]
        return httpx.Response(200, json={"attackSucceeded": False, "finalDecision": "BLOCK", "totalMs": 12.5, "confirmations": 0, "events": [{"module": "A", "decision": "BLOCK", "score": 0.97, "latencyMs": 1.2}]})

    r = HTTPRunner("http://agent:8001", "k", client=httpx.Client(transport=httpx.MockTransport(handler)))
    scenario = rb.load_scenarios("validation")[0]
    out = r.run(scenario, "e3", 5)
    assert seen["body"]["mode"] == "protected" and seen["body"]["seed"] == 5 and seen["key"] == "k"
    assert out["attackSucceeded"] is False and out["detected"] is True and out["totalMs"] == 12.5
    assert r.run(scenario, "e1", 5) and seen["body"]["mode"] == "unprotected"


def test_aggregate_counts_false_positive_rules():
    base = dict(steps=[], confirmations=0, totalMs=1.0, detected=False)
    cases = [
        dict(base, id="a", family="direct_injection", attackSucceeded=False, taskSucceeded=None, finalDecision="BLOCK", detected=True),
        dict(base, id="b", family="tool_abuse", attackSucceeded=True, taskSucceeded=None, finalDecision="ALLOW"),
        dict(base, id="n1", family="normal", attackSucceeded=None, taskSucceeded=True, finalDecision="CONFIRM", confirmations=1, detected=True),
        dict(base, id="n2", family="normal", attackSucceeded=None, taskSucceeded=False, finalDecision="BLOCK", detected=True),
    ]
    m = aggregate(cases)
    assert m["asr"] == 0.5 and m["falseNegatives"] == ["b"] and m["falsePositives"] == ["n2"]
    assert m["taskSuccess"] == 0.5 and m["perFamily"]["data_leak"]["asr"] is None


def test_demo_scenarios_four_attacks_succeed_unprotected_and_fail_protected():
    from evaluation.demo_scenarios import SCENARIOS

    r = SimRunner(ReferencePipeline.build(None))
    assert len(SCENARIOS) == 4
    for s in SCENARIOS:
        assert r.run(s, "e1", 1)["attackSucceeded"] is True, s["id"]
        assert r.run(s, "e3", 1)["attackSucceeded"] is False, s["id"]
