"""AS-S2-011 / AS-S2-013 : Policy Decision Engine.

Le §10 du dossier de conception (tableau de décision) N'ÉTAIT PAS DISPONIBLE : ces tests couvrent chaque règle de la table reconstituée
d'après le plan Agile et policy.yaml (voir docs/ai-service-engine.md), pas « chaque ligne du §10 ». Les identifiants de règles
(P1.*, P2.*, T.*, S.*, A.*) sont ceux du moteur.
"""
import json
import os
from pathlib import Path

import jsonschema
import pytest
import yaml

from app.core.config import POLICY_PATH
from app.core.engine import PolicyDecisionEngine, SessionState, Stage, worst
from app.core.policy import PolicyStore, load_policy, parse_policy
from app.models.verdict import Verdict

SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "docs/contract/verdict.schema.json").read_text(encoding="utf-8"))
BASE = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))


def pol(**changes):
    data = json.loads(json.dumps(BASE))
    for dotted, value in changes.items():
        node = data
        *path, last = dotted.split(".")
        for key in path:
            node = node.setdefault(key, {})
        node[last] = value
    return parse_policy(yaml.safe_dump(data))


def engine(policy=None):
    return PolicyDecisionEngine(policy or load_policy(POLICY_PATH))


def V(module, score=0.0, risk="low", attack="none", **meta):
    return Verdict(module=module, score=score, attack_type=attack, reason=f"verdict {module}", risk_level=risk, correlation_id="c-1", metadata=meta)


def C(*kinds, risk="low"):
    findings = [{"kind": k, "detail": f"détail {k}"} for k in kinds]
    return V("C", 1.0 if any(k in {"tool_not_allowed", "invalid_arguments", "unexpected_parameter", "path_bypass", "canary_in_arguments"} for k in kinds) else (0.5 if kinds else 0.0), risk, "tool_abuse" if kinds else "none", findings=findings)


def D(canary=False, kinds=(), score=0.0):
    return V("D", score, canary=canary, kinds=list(kinds))


def decide(stage, verdicts, session=None, policy=None):
    return engine(policy).decide(stage, verdicts, session, "c-1")


# ================================================================== TABLE DE DÉCISION : une ligne = un cas (≥ 25)
TABLE = [
    # (id, étape, verdicts, décision, règle)
    ("A score 0", Stage.INPUT, [V("A", 0.0)], "ALLOW", "A.below_review"),
    ("A juste sous la revue", Stage.INPUT, [V("A", 0.4999)], "ALLOW", "A.below_review"),
    ("A = seuil de revue", Stage.INPUT, [V("A", 0.5)], "CONFIRM", "T.review.confirm"),
    ("A bande de revue", Stage.INPUT, [V("A", 0.7)], "CONFIRM", "T.review.confirm"),
    ("A juste sous le blocage", Stage.INPUT, [V("A", 0.8999)], "CONFIRM", "T.review.confirm"),
    ("A = seuil de blocage", Stage.INPUT, [V("A", 0.9)], "BLOCK", "T.block"),
    ("A score 1", Stage.INPUT, [V("A", 1.0)], "BLOCK", "T.block"),
    ("B sous la revue", Stage.TOOL_RESULT, [V("B", 0.3)], "ALLOW", "A.below_review"),
    ("B bande de revue : nettoyage", Stage.TOOL_RESULT, [V("B", 0.5)], "SANITIZE", "T.review.sanitize"),
    ("B = seuil de blocage", Stage.TOOL_RESULT, [V("B", 0.9)], "BLOCK", "T.block"),
    ("C sans constat", Stage.TOOL_CALL, [C()], "ALLOW", "A.tool_ok"),
    ("C outil hors liste blanche", Stage.TOOL_CALL, [C("tool_not_allowed")], "BLOCK", "P1.tool_not_allowed"),
    ("C arguments invalides", Stage.TOOL_CALL, [C("invalid_arguments")], "BLOCK", "P1.invalid_arguments"),
    ("C paramètre non autorisé", Stage.TOOL_CALL, [C("unexpected_parameter")], "BLOCK", "P1.unexpected_parameter"),
    ("C contournement de chemin", Stage.TOOL_CALL, [C("path_bypass")], "BLOCK", "P1.path_bypass"),
    ("C canary dans les arguments", Stage.TOOL_CALL, [C("canary_in_arguments")], "BLOCK", "P1.canary_outgoing"),
    ("C confirmation obligatoire", Stage.TOOL_CALL, [C("requires_confirmation", risk="high")], "CONFIRM", "P2.requires_confirmation"),
    ("C destinataire inconnu", Stage.TOOL_CALL, [C("unknown_recipient", risk="medium")], "CONFIRM", "P2.unknown_recipient"),
    ("C chemin sensible", Stage.TOOL_CALL, [C("sensitive_path")], "CONFIRM", "P2.sensitive_path"),
    ("C action incohérente", Stage.TOOL_CALL, [C("action_incoherent")], "CONFIRM", "P2.incoherent_action"),
    ("C cohérence indisponible", Stage.TOOL_CALL, [C("coherence_unavailable")], "CONFIRM", "P2.coherence_unavailable"),
    ("D arguments sans secret", Stage.TOOL_CALL, [D()], "ALLOW", "A.args_clean"),
    ("D secret (clé API) dans les arguments", Stage.TOOL_CALL, [D(kinds=["api_key"])], "SANITIZE", "S.secret_masked"),
    ("D e-mail seul dans les arguments : destinataire légitime", Stage.TOOL_CALL, [D(kinds=["email"])], "ALLOW", "A.args_clean"),
    ("D canary dans un outil sortant", Stage.TOOL_CALL, [D(canary=True, kinds=["api_key"])], "BLOCK", "P1.canary_outgoing"),
    ("D réponse propre", Stage.FINAL_RESPONSE, [D()], "ALLOW", "A.output_clean"),
    ("D donnée sensible dans la réponse", Stage.FINAL_RESPONSE, [D(kinds=["iban"])], "SANITIZE", "S.secret_masked"),
    ("D e-mail dans la réponse (comportement de Fati conservé)", Stage.FINAL_RESPONSE, [D(kinds=["email"])], "SANITIZE", "S.secret_masked"),
    ("D canary dans la réponse : masqué et signalé", Stage.FINAL_RESPONSE, [D(canary=True, kinds=["api_key"])], "SANITIZE", "S.canary_in_response"),
    ("aucun verdict", Stage.INPUT, [], "ALLOW", "A.no_verdict"),
]


@pytest.mark.parametrize("name,stage,verdicts,decision,rule", TABLE, ids=[t[0] for t in TABLE])
def test_decision_table(name, stage, verdicts, decision, rule):
    d = decide(stage, verdicts)
    assert (d.decision, d.rule) == (decision, rule), d.reason
    assert d.verdict.decision == decision and d.verdict.module == "ENGINE" and d.stage == stage.value


def test_table_covers_all_four_decisions_and_every_rule_family():
    assert {t[3] for t in TABLE} == {"ALLOW", "SANITIZE", "CONFIRM", "BLOCK"}
    rules = {t[4] for t in TABLE}
    assert {r.split(".")[0] for r in rules} == {"P1", "P2", "T", "S", "A"}


# ================================================================== PRIORITÉS : interdiction > confirmation > seuils > autorisation
def test_prohibition_beats_a_low_score():
    """Une interdiction explicite n'est jamais contournée par un score faible."""
    v = C("tool_not_allowed")
    assert v.score == 1.0
    low = V("C", 0.0, findings=[{"kind": "tool_not_allowed", "detail": "x"}])  # score artificiellement bas
    d = decide(Stage.TOOL_CALL, [low])
    assert d.decision == "BLOCK" and d.rule == "P1.tool_not_allowed"


def test_prohibition_beats_confirmation_in_the_same_verdict():
    d = decide(Stage.TOOL_CALL, [C("requires_confirmation", "sensitive_path", "path_bypass")])
    assert d.decision == "BLOCK" and d.rule == "P1.path_bypass"


def test_confirmation_condition_beats_a_low_score_but_not_a_blocking_score():
    assert decide(Stage.INPUT, [V("A", 0.1)]).decision == "ALLOW"
    assert decide(Stage.TOOL_CALL, [V("A", 0.1), C("requires_confirmation")]).decision == "CONFIRM"
    assert decide(Stage.TOOL_CALL, [V("A", 0.95), C("requires_confirmation")]).decision == "BLOCK"


def test_threshold_rule_loses_to_prohibition_rule_on_equal_severity():
    d = decide(Stage.TOOL_CALL, [V("A", 0.95), C("tool_not_allowed")])
    assert d.decision == "BLOCK" and d.rule == "P1.tool_not_allowed"  # P1 prioritaire sur T.block pour la raison


def test_confirmation_rule_wins_the_reason_over_a_sanitize_threshold():
    d = decide(Stage.TOOL_CALL, [V("B", 0.6), C("unknown_recipient")])
    assert d.decision == "CONFIRM" and d.rule == "P2.unknown_recipient"


# ================================================================== AGRÉGATION ET CONFLITS : décision la plus sévère
@pytest.mark.parametrize(
    "verdicts,decision",
    [
        ([V("A", 0.0), C()], "ALLOW"),
        ([C(), D(kinds=["api_key"])], "SANITIZE"),
        ([C("requires_confirmation"), D(kinds=["api_key"])], "CONFIRM"),
        ([C("tool_not_allowed"), D()], "BLOCK"),
        ([C("requires_confirmation"), D(canary=True)], "BLOCK"),
        ([V("A", 0.6), V("B", 0.95)], "BLOCK"),
        ([V("A", 0.6), V("B", 0.6)], "CONFIRM"),
    ],
)
def test_conflicting_verdicts_resolve_to_the_most_severe(verdicts, decision):
    assert decide(Stage.TOOL_CALL, verdicts).decision == decision


def test_allow_never_overrides_a_block_whatever_the_order():
    for order in ([V("A", 0.0), C("tool_not_allowed")], [C("tool_not_allowed"), V("A", 0.0)]):
        assert decide(Stage.TOOL_CALL, order).decision == "BLOCK"


def test_per_module_contributions_are_reported():
    d = decide(Stage.TOOL_CALL, [C("requires_confirmation"), D(kinds=["api_key"])])
    assert d.per_module == {"C": "CONFIRM", "D": "SANITIZE"}
    assert [c.module for c in d.contributions] == ["C", "D"]


def test_tied_rules_are_merged_in_the_reason_and_listed_in_the_metadata():
    d = decide(Stage.TOOL_CALL, [C("sensitive_path", "requires_confirmation")])
    assert d.decision == "CONFIRM" and "détail sensitive_path" in d.reason and "détail requires_confirmation" in d.reason
    assert d.verdict.metadata["contributions"][0]["rules"] == ["P2.sensitive_path", "P2.requires_confirmation"]


def test_unknown_finding_is_a_confirmation_never_a_silent_allow():
    d = decide(Stage.TOOL_CALL, [C("nouveau_constat")])
    assert d.decision == "CONFIRM" and d.rule == "P2.unknown_finding"


def test_worst_helper_and_severity_order():
    assert worst([]) == "ALLOW" and worst(["ALLOW", "SANITIZE"]) == "SANITIZE" and worst(["SANITIZE", "CONFIRM", "ALLOW"]) == "CONFIRM" and worst(["CONFIRM", "BLOCK"]) == "BLOCK"


# ================================================================== SEUILS (0,5 et 0,9, lus dans la politique)
@pytest.mark.parametrize("score,decision", [(0.0, "ALLOW"), (0.49, "ALLOW"), (0.4999999, "ALLOW"), (0.5, "CONFIRM"), (0.50000001, "CONFIRM"), (0.89, "CONFIRM"), (0.8999999, "CONFIRM"), (0.9, "BLOCK"), (0.9000001, "BLOCK"), (1.0, "BLOCK")])
def test_threshold_boundaries_are_inclusive_at_the_lower_edge(score, decision):
    assert decide(Stage.INPUT, [V("A", score)]).decision == decision


def test_thresholds_are_the_ones_of_the_policy_file():
    p = load_policy(POLICY_PATH)
    assert (p.thresholds.injection_review, p.thresholds.injection_block) == (0.5, 0.9)


def test_changed_thresholds_change_decisions():
    p = pol(**{"thresholds.injection_review": 0.2, "thresholds.injection_block": 0.4})
    assert decide(Stage.INPUT, [V("A", 0.3)], policy=p).decision == "CONFIRM"
    assert decide(Stage.INPUT, [V("A", 0.4)], policy=p).decision == "BLOCK"
    assert decide(Stage.INPUT, [V("A", 0.19)], policy=p).decision == "ALLOW"


def test_equal_thresholds_leave_no_review_band():
    p = pol(**{"thresholds.injection_review": 0.7, "thresholds.injection_block": 0.7})
    assert decide(Stage.INPUT, [V("A", 0.69)], policy=p).decision == "ALLOW" and decide(Stage.INPUT, [V("A", 0.7)], policy=p).decision == "BLOCK"


def test_review_action_is_configurable_per_stage():
    p = pol(**{"decisions.review_action.input": "SANITIZE", "decisions.review_action.tool_result": "BLOCK"})
    assert decide(Stage.INPUT, [V("A", 0.6)], policy=p).decision == "SANITIZE"
    assert decide(Stage.TOOL_RESULT, [V("B", 0.6)], policy=p).decision == "BLOCK"
    assert decide(Stage.TOOL_RESULT, [V("B", 0.6)], policy=p).rule == "T.review.block"


# ================================================================== POLITIQUE : les décisions viennent du fichier, pas du code
@pytest.mark.parametrize(
    "change,verdicts,decision,rule",
    [
        ({"decisions.on_unknown_recipient": "BLOCK"}, [C("unknown_recipient")], "BLOCK", "P1.unknown_recipient"),
        ({"decisions.on_sensitive_path": "BLOCK"}, [C("sensitive_path")], "BLOCK", "P1.sensitive_path"),
        ({"decisions.on_incoherent_action": "BLOCK"}, [C("action_incoherent")], "BLOCK", "P1.incoherent_action"),
        ({"decisions.on_coherence_unavailable": "BLOCK"}, [C("coherence_unavailable")], "BLOCK", "P2.coherence_unavailable"),
        ({"output.on_canary_in_outgoing_tool": "CONFIRM"}, [C("canary_in_arguments")], "CONFIRM", "P2.canary_outgoing"),
        ({"output.on_canary_in_outgoing_tool": "CONFIRM"}, [D(canary=True)], "CONFIRM", "P2.canary_outgoing"),
        ({"output.on_secret_detected": "BLOCK"}, [D(kinds=["api_key"])], "BLOCK", "S.secret_masked"),
        ({"output.mask_patterns": ["email"]}, [D(kinds=["email"])], "SANITIZE", "S.secret_masked"),
    ],
)
def test_decisions_follow_the_policy(change, verdicts, decision, rule):
    stage = Stage.FINAL_RESPONSE if verdicts[0].module == "D" and "output.on_canary_in_outgoing_tool" not in change else Stage.TOOL_CALL
    d = decide(stage, verdicts, SessionState(), pol(**change))
    assert (d.decision, d.rule) == (decision, rule)


def test_hot_reloaded_threshold_is_used_by_the_next_decision(tmp_path):
    path = tmp_path / "policy.yaml"
    path.write_text(POLICY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    eng = PolicyDecisionEngine(PolicyStore(path))
    assert eng.decide(Stage.INPUT, [V("A", 0.85)]).decision == "CONFIRM"
    path.write_text(path.read_text(encoding="utf-8").replace("injection_block: 0.90", "injection_block: 0.80"), encoding="utf-8")
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))
    assert eng.decide(Stage.INPUT, [V("A", 0.85)]).decision == "BLOCK"


def test_invalid_reload_keeps_deciding_with_the_previous_policy(tmp_path):
    path = tmp_path / "policy.yaml"
    path.write_text(POLICY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    eng = PolicyDecisionEngine(PolicyStore(path))
    path.write_text("cassé", encoding="utf-8")
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))
    assert eng.decide(Stage.INPUT, [V("A", 0.95)]).decision == "BLOCK" and eng.decide(Stage.INPUT, [V("A", 0.1)]).decision == "ALLOW"


# ================================================================== SESSION ET ESCALADE (hypothèse R2, à valider)
def test_incoherent_action_is_confirm_without_prior_injection():
    d = decide(Stage.TOOL_CALL, [C("action_incoherent")], SessionState())
    assert (d.decision, d.escalated) == ("CONFIRM", False)


def test_incoherent_action_is_block_after_an_indirect_injection_was_detected():
    s = SessionState()
    engine().decide(Stage.TOOL_RESULT, [V("B", 0.95, attack="indirect_injection")], s)
    assert s.indirect_injection_detected is True
    d = decide(Stage.TOOL_CALL, [C("action_incoherent")], s)
    assert (d.decision, d.rule, d.escalated) == ("BLOCK", "P1.incoherent_after_injection", True)


def test_review_band_detection_by_guard_b_also_arms_the_escalation():
    s = SessionState()
    assert engine().decide(Stage.TOOL_RESULT, [V("B", 0.55)], s).decision == "SANITIZE"
    assert s.indirect_injection_detected is True


def test_clean_tool_result_does_not_arm_the_escalation():
    s = SessionState()
    engine().decide(Stage.TOOL_RESULT, [V("B", 0.49)], s)
    assert s.indirect_injection_detected is False


def test_escalation_only_concerns_incoherence():
    s = SessionState(indirect_injection_detected=True)
    assert decide(Stage.TOOL_CALL, [C("sensitive_path")], s).decision == "CONFIRM"
    assert decide(Stage.TOOL_CALL, [C("requires_confirmation")], s).decision == "CONFIRM"
    assert decide(Stage.TOOL_CALL, [C()], s).decision == "ALLOW"


def test_sessions_are_independent():
    a, b = SessionState(), SessionState()
    engine().decide(Stage.TOOL_RESULT, [V("B", 0.95)], a)
    assert b.indirect_injection_detected is False and decide(Stage.TOOL_CALL, [C("action_incoherent")], b).decision == "CONFIRM"


def test_escalation_target_is_configurable():
    p = pol(**{"decisions.on_incoherent_after_indirect_injection": "CONFIRM"})
    assert decide(Stage.TOOL_CALL, [C("action_incoherent")], SessionState(indirect_injection_detected=True), p).decision == "CONFIRM"


# ================================================================== VERDICT ENGINE : contrat partagé
def test_engine_verdict_conforms_to_the_shared_schema():
    d = decide(Stage.TOOL_CALL, [C("requires_confirmation", risk="high"), D()])
    out = d.verdict.to_dict()
    jsonschema.validate(out, SCHEMA)
    assert out["module"] == "ENGINE" and out["decision"] == "CONFIRM" and out["correlationId"] == "c-1" and out["metadata"]["rule"] == "P2.requires_confirmation"
    assert out["reason"].startswith("[P2.requires_confirmation]")


def test_engine_does_not_modify_the_guard_verdicts():
    vs = [V("A", 0.6), V("B", 0.2)]
    before = [v.to_dict() for v in vs]
    decide(Stage.INPUT, vs)
    assert [v.to_dict() for v in vs] == before and all(v.decision is None for v in vs)


def test_score_is_the_maximum_and_risk_level_is_a_distinct_field():
    d = decide(Stage.TOOL_CALL, [C("requires_confirmation", risk="high"), D()])
    assert d.verdict.score == 0.5 and d.verdict.risk_level == "high"  # risque de l'outil (high) ≠ niveau déduit du score (medium)
    d = decide(Stage.INPUT, [V("A", 0.95)])
    assert d.verdict.score == 0.95 and d.verdict.risk_level == "high"
    d = decide(Stage.INPUT, [V("A", 0.1)])
    assert d.verdict.score == 0.1 and d.verdict.risk_level == "low"


def test_risk_level_uses_the_policy_thresholds_not_hardcoded_ones():
    p = pol(**{"thresholds.injection_review": 0.2, "thresholds.injection_block": 0.4})
    assert decide(Stage.INPUT, [V("A", 0.3)], policy=p).verdict.risk_level == "medium"
    assert decide(Stage.INPUT, [V("A", 0.45)], policy=p).verdict.risk_level == "high"


def test_degraded_and_attack_type_are_propagated():
    v = Verdict(module="B", score=0.95, attack_type="indirect_injection", reason="x", risk_level="high", degraded=True)
    d = decide(Stage.TOOL_RESULT, [v])
    assert d.verdict.degraded is True and d.verdict.attack_type == "indirect_injection"
    assert decide(Stage.INPUT, [V("A", 0.1)]).verdict.attack_type == "none"


def test_canary_is_flagged_in_the_decision_and_the_verdict():
    d = decide(Stage.FINAL_RESPONSE, [D(canary=True, kinds=["api_key"])])
    assert d.canary is True and d.verdict.metadata["canary"] is True and "canary" in d.verdict.metadata["flags"] and "canary signalé" in d.reason


def test_policy_digest_is_recorded_when_a_store_is_used(tmp_path):
    path = tmp_path / "policy.yaml"
    path.write_text(POLICY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    store = PolicyStore(path)
    d = PolicyDecisionEngine(store).decide(Stage.INPUT, [V("A", 0.0)])
    assert d.verdict.metadata["policy"] == store.digest[:12]
    assert "policy" not in decide(Stage.INPUT, [V("A", 0.0)]).verdict.metadata  # politique figée : pas d'empreinte


def test_decision_is_deterministic():
    runs = {json.dumps(decide(Stage.TOOL_CALL, [C("sensitive_path", "requires_confirmation"), D(kinds=["api_key"])]).verdict.to_dict()["metadata"], sort_keys=True) for _ in range(5)}
    assert len(runs) == 1


def test_engine_never_leaks_argument_values():
    d = decide(Stage.TOOL_CALL, [C("canary_in_arguments")])
    assert "sk-FAKE-1234" not in json.dumps(d.verdict.to_dict())
