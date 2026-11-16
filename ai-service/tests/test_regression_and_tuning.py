import json

import pytest

from evaluation import compare_classifiers as cc
from evaluation import run_regression as rr
from evaluation import tune_thresholds as tt


def test_regression_runner_passes_on_committed_baseline(capsys):
    assert rr.main([]) == 0


def test_regression_detects_previously_correct_case_now_wrong(tmp_path):
    current = rr.current_outcomes()
    key = next(k for k, v in current.items() if v["correct"])
    baseline = {k: dict(v) for k, v in current.items()}
    broken = {k: dict(v) for k, v in current.items()}
    broken[key]["correct"] = False
    regressions, fixed, new = rr.compare(baseline, broken)
    assert regressions == [key] and not fixed and not new
    path = tmp_path / "b.json"
    path.write_text(json.dumps({"cases": baseline}))
    # un cas mal classé dans la référence puis corrigé n'est pas une régression
    regressions, fixed, _ = rr.compare(broken, baseline)
    assert not regressions and fixed == [key]


def test_regression_never_reads_test_split():
    from evaluation.dataio import load_split

    assert "test" not in rr.REGRESSION_SPLITS
    test_ids = {e.id for e in load_split("test")}
    assert not any(k.split(":")[-1] in test_ids for k in rr.current_outcomes())
    baseline_keys = json.loads(rr.BASELINE_PATH.read_text(encoding="utf-8"))["cases"]
    assert not any(k.split(":")[-1] in test_ids for k in baseline_keys)


def test_update_writes_baseline(tmp_path):
    path = tmp_path / "base.json"
    assert rr.main(["--update", "--baseline", str(path)]) == 0
    assert json.loads(path.read_text())["cases"]
    assert rr.main(["--baseline", str(path)]) == 0


TH = {"injection_review": 0.5, "injection_block": 0.9, "coherence_min": 0.4}


def test_choose_keeps_start_values_on_wide_plateau():
    y = [1] * 10 + [0] * 10
    s = [0.95] * 10 + [0.05] * 10
    chosen, why = tt.choose(y, s, TH)
    assert chosen["injection_review"] == 0.5 and chosen["injection_block"] == 0.9
    assert any("petit" in line for line in why)


def test_choose_respects_fpr_budget():
    y = [1, 1, 1, 1, 0, 0, 0, 0]
    s = [0.9, 0.8, 0.7, 0.3, 0.6, 0.2, 0.1, 0.1]
    chosen, _ = tt.choose(y, s, TH, max_fpr=0.0)
    assert chosen["injection_review"] > 0.6  # 0,6 est un faux positif : le seuil doit le dépasser


def test_choose_falls_back_when_budget_impossible():
    y = [1, 0]
    s = [0.2, 0.9]
    chosen, why = tt.choose(y, s, TH, max_fpr=0.0)
    assert chosen == TH and "conservée" in why[0]


def test_block_never_below_floor_nor_too_close_to_review():
    y = [1] * 20 + [0] * 20
    s = [0.99] * 20 + [0.01] * 20
    chosen, _ = tt.choose(y, s, TH)
    assert chosen["injection_block"] >= tt.BLOCK_FLOOR and chosen["injection_block"] >= chosen["injection_review"] + 0.05


def test_update_policy_rewrites_only_thresholds(tmp_path):
    p = tmp_path / "policy.yaml"
    p.write_text("thresholds:                  # TEMPORARY\n  injection_block: 0.90\n  injection_review: 0.50\n  coherence_min: 0.40\noutput:\n  canary_tokens: [sk-FAKE-1234]\n")
    tt.update_policy(p, {"injection_block": 0.85, "injection_review": 0.45, "coherence_min": 0.4})
    text = p.read_text()
    assert "injection_block: 0.85" in text and "injection_review: 0.45" in text and "GELÉS" in text and "sk-FAKE-1234" in text


def test_tuning_script_never_reads_test_split(monkeypatch):
    from evaluation import dataio

    requested = []
    original = dataio.load_split
    monkeypatch.setattr(tt, "load_split", lambda name, *a, **k: requested.append(name) or original(name, *a, **k))
    tt.collect_scores(False)
    assert requested == ["validation"]


def test_adr_decision_follows_the_numbers():
    rows = {
        "a": {"measured": True, "fpr": 0.0, "recall": 0.9, "f1": 0.9},
        "b": {"measured": True, "fpr": 0.2, "recall": 1.0, "f1": 0.95},
        "c": {"measured": False, "reason": "absent"},
    }
    best, text = cc.pick(rows)
    assert best == "a" and "`b`" in text
    assert cc.pick({"x": {"measured": True, "fpr": 0.5, "recall": 1.0, "f1": 1.0}})[0] is None


@pytest.mark.parametrize("bad", ["rules", "tfidf"])
def test_candidate_names_present(bad):
    assert bad in cc.compare([]).keys()
