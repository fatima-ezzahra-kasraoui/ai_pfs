import json

import jsonschema
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.guards.content_guard import ContentGuard
from app.guards.input_guard import InputGuard
from app.guards.output_guard import OutputGuard
from app.main import create_app
from evaluation import make_tables as mt
from evaluation import results as res
from evaluation import run_benchmark as rb
from evaluation.runners import SimRunner
from evaluation.sim.pipeline import ReferencePipeline

H = {"X-AI-Service-Key": "k"}


@pytest.fixture(scope="module")
def results_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("results")
    runner = SimRunner(ReferencePipeline.build(None))
    rb.run("validation", ["e1", "e2", "e3"], runner, 3, out_dir=d)
    return d


def make(**kw):
    base = dict(kind="detection", name="x", split="validation", status="preliminary", seed=1, config={}, metrics={})
    base.update(kw)
    return res.make_result(**base)


def test_invalid_result_refused_not_ignored(tmp_path):
    bad = make()
    bad["status"] = "official"  # validation ne peut pas être « official »
    with pytest.raises(jsonschema.ValidationError):
        res.write_result(bad, tmp_path)
    test_prelim = make(split="test", status="preliminary")
    with pytest.raises(jsonschema.ValidationError):
        res.write_result(test_prelim, tmp_path)
    (tmp_path / "corrompu.json").write_text(json.dumps({"kind": "detection"}))
    with pytest.raises(jsonschema.ValidationError):
        res.load_results(tmp_path)


def test_result_records_commit_and_timestamp(tmp_path):
    data = make()
    assert data["generatedAt"] and data["commit"] and isinstance(data["dirty"], bool)
    path = res.write_result(data, tmp_path)
    assert res.load_results(tmp_path)[0]["_file"] == path.name


def test_metrics_endpoint_returns_file_values_unchanged(results_dir):
    client = TestClient(create_app(Settings("k"), {"A": InputGuard(), "B": ContentGuard(), "D": OutputGuard()}, results_dir))
    body = client.get("/internal/metrics", headers=H).json()
    assert body["status"] == "ok"
    stored = {r["name"]: r for r in res.load_results(results_dir)}
    for item in body["results"]:
        assert item["metrics"]["asr"] == stored[item["name"]]["metrics"]["asr"]
        assert "errors" not in item["metrics"] and "cases" not in item
    only_official = client.get("/internal/metrics?include_preliminary=false", headers=H).json()
    assert only_official["status"] == "not_available" and only_official["results"] == []


def test_table_values_match_result_files_and_cite_sources(results_dir, tmp_path):
    results = res.load_results(results_dir)
    rows, runs = mt.build_rows(results, "validation", "preliminary")
    glob = rows[-1]
    assert glob[0] == "Global"
    assert glob[1] == mt._pct(runs["e1"]["metrics"]["asr"])
    assert glob[3] == mt._pct(runs["e3"]["metrics"]["asr"])
    for row in rows:
        assert all(r["_file"] in row[-1] for r in runs.values() if r)
    # recalcul indépendant depuis les cas bruts
    e3 = runs["e3"]
    atk = [c for c in e3["cases"] if c["family"] != "normal"]
    assert mt._pct(sum(c["attackSucceeded"] for c in atk) / len(atk)) == glob[3]


def test_table_without_results_prints_na_not_numbers(tmp_path):
    rows, runs = mt.build_rows([], "test", "official")
    assert all(v is None for v in runs.values())
    for row in rows:
        assert all(cell in {"n/a", "—", "aucun résultat"} or cell.isalpha() or " " in cell for cell in row[1:-1])
        assert "%" not in "".join(row[1:])


def test_make_tables_cli_writes_md_csv_and_failures(results_dir, tmp_path):
    out = tmp_path / "out"
    assert mt.main(["--results-dir", str(results_dir), "--out-dir", str(out)]) == 0
    md = (out / "table_validation_preliminary.md").read_text(encoding="utf-8")
    assert "agent simulé" in md and "e3_validation_" in md
    assert (out / "table_validation_preliminary.csv").read_text(encoding="utf-8").count("\n") == 6
    assert "Échecs" in (out / "failures_validation_preliminary.md").read_text(encoding="utf-8")
