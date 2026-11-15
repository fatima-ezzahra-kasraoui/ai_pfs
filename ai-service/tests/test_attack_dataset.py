import json

from evaluation.attacks.build_dataset import FAMILIES, OUT_DIR, build
from evaluation.dataio import load_split
from evaluation.run_benchmark import load_scenarios


def test_at_least_10_per_family_and_normals_in_each_split():
    for split in ("validation", "test"):
        rows = load_scenarios(split)
        for fam in FAMILIES:
            assert sum(r["family"] == fam for r in rows) >= 10, (split, fam)
        assert sum(r["family"] == "normal" for r in rows) >= 10


def test_splits_disjoint_by_id_and_by_message():
    val, test = load_scenarios("validation"), load_scenarios("test")
    assert not ({r["id"] for r in val} & {r["id"] for r in test})
    msgs = lambda rs: {(r["user_message"], (r["tool"] or {}).get("content")) for r in rs}  # noqa: E731
    assert not (msgs(val) & msgs(test))


def test_every_case_has_source_and_no_real_data():
    for split in ("validation", "test"):
        for r in load_scenarios(split):
            assert r["source"]
            blob = json.dumps(r, ensure_ascii=False)
            assert "@gmail" not in blob and "@outlook" not in blob and "@yahoo" not in blob


def test_attacks_have_goal_and_normals_have_legit_goal():
    for split in ("validation", "test"):
        for r in load_scenarios(split):
            if r["family"] == "normal":
                assert r["legit_goal"] and r["attack_goal"] is None
            else:
                assert r["attack_goal"] and r["legit_goal"] is None


def test_direct_injection_messages_come_from_matching_detection_split():
    for split in ("validation", "test"):
        texts = {e.text for e in load_split(split) if e.label == 1}
        for r in load_scenarios(split):
            if r["family"] == "direct_injection":
                assert r["user_message"] in texts


def test_committed_dataset_is_reproducible():
    for split in ("validation", "test"):
        on_disk = [json.loads(line) for line in (OUT_DIR / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()]
        assert build(split) == on_disk


def test_indirect_scenarios_hide_or_show_instruction_in_content():
    for r in load_scenarios("validation"):
        if r["family"] == "indirect_injection":
            assert r["injected_instruction"] in r["tool"]["content"]
