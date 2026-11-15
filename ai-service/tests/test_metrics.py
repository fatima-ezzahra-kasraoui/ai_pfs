import pytest

from evaluation import metrics as m


def test_confusion_and_basic_metrics_hand_computed():
    y_true = [1, 1, 1, 1, 0, 0, 0, 0, 0, 0]
    y_pred = [1, 1, 1, 0, 1, 0, 0, 0, 0, 0]
    c = m.confusion(y_true, y_pred)
    assert (c.tp, c.fp, c.tn, c.fn) == (3, 1, 5, 1)
    assert m.precision(c) == pytest.approx(3 / 4)
    assert m.recall(c) == pytest.approx(3 / 4)
    assert m.f1(c) == pytest.approx(0.75)
    assert m.false_positive_rate(c) == pytest.approx(1 / 6)


def test_undefined_metrics_are_none_not_zero():
    c = m.confusion([0, 0], [0, 0])
    assert m.precision(c) is None and m.recall(c) is None and m.f1(c) is None
    assert m.false_positive_rate(c) == 0.0
    c2 = m.confusion([1, 1], [0, 0])
    assert m.precision(c2) is None and m.recall(c2) == 0.0 and m.f1(c2) is None
    c3 = m.confusion([1], [1])
    assert m.false_positive_rate(c3) is None


def test_confusion_validation():
    with pytest.raises(ValueError):
        m.confusion([1], [1, 0])
    with pytest.raises(ValueError):
        m.confusion([2], [1])


def test_asr_task_success_confirmation_rate():
    assert m.attack_success_rate([True, False, False, True]) == 0.5
    assert m.attack_success_rate([]) is None
    assert m.task_success_rate([True, True, False]) == pytest.approx(2 / 3)
    assert m.confirmation_rate(["ALLOW", "CONFIRM", "BLOCK", "CONFIRM"]) == 0.5
    assert m.confirmation_rate([]) is None


def test_percentile_interpolation():
    xs = [10, 20, 30, 40]
    assert m.percentile(xs, 0) == 10 and m.percentile(xs, 100) == 40
    assert m.percentile(xs, 50) == pytest.approx(25)
    assert m.percentile([], 50) is None
    with pytest.raises(ValueError):
        m.percentile(xs, 101)


def test_latency_summary():
    s = m.latency_summary([1.0, 2.0, 3.0])
    assert s["n"] == 3 and s["mean"] == pytest.approx(2.0) and s["p50"] == 2.0 and s["max"] == 3.0
    assert m.latency_summary([])["mean"] is None


def test_threshold_sweep_monotonic_recall():
    y = [1, 1, 0, 0]
    scores = [0.9, 0.6, 0.55, 0.1]
    rows = m.threshold_sweep(y, scores, [0.5, 0.7, 0.95])
    recalls = [r["recall"] for r in rows]
    assert recalls == sorted(recalls, reverse=True)
    assert rows[0]["fpr"] == pytest.approx(0.5) and rows[1]["fpr"] == 0.0
