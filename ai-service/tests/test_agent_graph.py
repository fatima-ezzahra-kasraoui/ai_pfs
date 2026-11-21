"""AS-S1-022 : agent LangGraph (flux, guards obligatoires, erreurs, reproductibilité)."""
import pytest

from app.agent.hooks import Gate, PassthroughHooks
from app.agent.service import (
    AgentService,
    ConfigurationError,
    PolicyUnavailableError,
    RunInput,
    demo_catalog,
    evaluate_outcome,
    resolve_mode,
)
from app.agent.state import Event
from app.guards.content_guard import ContentGuard
from app.guards.input_guard import InputGuard
from app.guards.output_guard import OutputGuard
from app.llm import LLMProviderError, LLMResponse, LLMTimeoutError, ToolCall
from app.llm.providers.mock import ScriptedLLM, SimulatedLLM

GUARDS = {"A": InputGuard(), "B": ContentGuard(), "D": OutputGuard()}
SCEN = demo_catalog()


def run(scenario_id, config, llm=None, policy="auto", **kw):
    s = SCEN[scenario_id]
    return AgentService(llm or SimulatedLLM(), GUARDS).run(RunInput(message=s["user_message"], scenario_id=scenario_id, tool_fixture=s["tool"], config=config, confirmation_policy=policy, seed=42, **kw))


# ------------------------------------------------------------------ scénarios du dossier
@pytest.mark.parametrize("sid", list(SCEN))
def test_unprotected_agent_is_attackable(sid):
    o = run(sid, "e1")
    assert o.attack_succeeded is True and o.events == [] and o.final_decision == "ALLOW" and o.mode == "unprotected"


@pytest.mark.parametrize("sid", list(SCEN))
def test_protected_agent_neutralises_attack(sid):
    o = run(sid, "e3")
    assert o.attack_succeeded is False and o.mode == "protected" and o.events and o.final_decision != "ALLOW"


def test_direct_injection_blocked_by_guard_a_before_any_llm_call():
    llm = ScriptedLLM([])  # tout appel lèverait
    o = run("demo-1-injection-directe", "e3", llm)
    assert o.halted == "input_blocked" and llm.calls == [] and o.events[0].module == "A" and o.events[0].decision == "BLOCK"


def test_indirect_injection_content_removed_by_guard_b():
    o = run("demo-2-injection-indirecte", "e3")
    assert any(e.module == "B" and e.decision == "BLOCK" for e in o.events) and o.outbox == []


def test_secret_masked_in_final_response_by_guard_d():
    o = run("demo-3-fuite-faux-secret", "e3")
    assert "sk-FAKE-1234" not in o.final_text and "sk-****" in o.final_text
    assert o.events[-1].stage == "final_response" and o.events[-1].decision == "SANITIZE"


def test_dangerous_tool_requires_confirmation_and_is_denied():
    o = run("demo-4-outil-dangereux", "e3")
    conf = [e for e in o.events if e.decision == "CONFIRM"]
    assert o.confirmations == 1 and conf[0].module == "C" and conf[0].confirmation == "denied" and o.deleted == [] and o.executed == []


def test_confirmation_policy_approve_executes_simulated_action():
    o = run("demo-4-outil-dangereux", "e3", policy="approve")
    assert o.confirmations == 1 and o.deleted == ["/documents/rapport_final.docx"] and o.attack_succeeded is True  # l'humain a approuvé : la protection n'est pas en cause
    assert o.executed[0]["sideEffect"] and o.executed[0]["simulated"] is True


def test_auto_policy_approves_legitimate_task():
    o = AgentService(SimulatedLLM(), GUARDS).run(RunInput(message="Supprime le fichier notes.txt", config="e3", confirmation_policy="auto", legit_goal={"kind": "tool_call", "tool": "delete_file", "path": "/documents/notes.txt"}))
    assert o.task_succeeded is True and o.attack_succeeded is None and o.deleted == ["/documents/notes.txt"]


def test_benign_request_is_not_disturbed_by_protection():
    o = AgentService(SimulatedLLM(), GUARDS).run(RunInput(message="Résume mes mails.", config="e3", legit_goal={"kind": "tool_call", "tool": "read_email"}))
    assert o.final_decision in {"ALLOW", "SANITIZE"} and o.task_succeeded is True and o.halted is None
    assert o.executed[0]["tool"] == "read_email"


# ------------------------------------------------------------------ garde-fous du flux
class CountingHooks(PassthroughHooks):
    protected = True

    def __init__(self):
        self.calls = []

    def check_input(self, text, cid):
        self.calls.append("input")
        return Gate()

    def check_tool_call(self, tool, args, cid):
        self.calls.append("tool_call")
        return Gate()

    def check_tool_content(self, tool, text, cid):
        self.calls.append("tool_content")
        return Gate()

    def check_final_response(self, text, cid):
        self.calls.append("final")
        return Gate()


def test_flow_always_traverses_every_hook_in_order():
    hooks = CountingHooks()
    svc = AgentService(SimulatedLLM(), GUARDS)
    svc._hooks = lambda config: hooks
    svc.run(RunInput(message="Résume mes mails.", config="e3"))
    assert hooks.calls == ["input", "tool_call", "tool_content", "final"]


def test_block_decision_on_tool_call_prevents_execution():
    class Deny(CountingHooks):
        def check_tool_call(self, tool, args, cid):
            return Gate("BLOCK", [Event("tool_call", "C", "BLOCK", None, "test")])

    svc = AgentService(SimulatedLLM(), GUARDS)
    svc._hooks = lambda config: Deny()
    o = svc.run(RunInput(message="Supprime le fichier notes.txt", config="e3"))
    assert o.executed == [] and o.deleted == [] and o.final_decision == "BLOCK"


def test_unknown_tool_from_llm_is_blocked_when_protected_and_errors_when_not():
    script = lambda: ScriptedLLM([LLMResponse(tool_calls=(ToolCall("t1", "execute_shell", {"cmd": "ls"}),)), LLMResponse(text="fin")])  # noqa: E731
    p = AgentService(script(), GUARDS).run(RunInput(message="x", config="e3"))
    assert any(e.module == "C" and e.decision == "BLOCK" for e in p.events) and p.executed == []
    u = AgentService(script(), GUARDS).run(RunInput(message="x", config="e1"))
    assert u.executed == [] and u.final_text == "fin"


def test_invalid_tool_arguments_do_not_crash_the_agent():
    llm = ScriptedLLM([LLMResponse(tool_calls=(ToolCall("t1", "read_file", {"mauvais": 1}),)), LLMResponse(text="ok")])
    o = AgentService(llm, GUARDS).run(RunInput(message="x", config="e1"))
    assert o.final_text == "ok" and "Erreur" in llm.calls[1][1][-1].content


def test_max_steps_bounds_a_looping_model():
    loop = ScriptedLLM([LLMResponse(tool_calls=(ToolCall(f"t{i}", "read_email", {}),)) for i in range(50)])
    o = AgentService(loop, GUARDS, max_steps=3).run(RunInput(message="x", config="e1"))
    assert o.halted == "max_steps" and o.steps == 3 and len(loop.calls) == 3


@pytest.mark.parametrize("exc", [LLMTimeoutError("t"), LLMProviderError("p", 500)])
def test_llm_error_is_reported_without_detail(exc):
    o = AgentService(ScriptedLLM([exc]), GUARDS).run(RunInput(message="x", config="e1"))
    assert o.halted == "llm_error" and o.error == type(exc).__name__ and "Le modèle de langage est indisponible" in o.final_text


def test_run_is_reproducible():
    a, b = run("demo-2-injection-indirecte", "e3"), run("demo-2-injection-indirecte", "e3")
    strip = lambda o: ([(e.stage, e.module, e.decision, e.score) for e in o.events], o.final_text, o.final_decision, o.attack_succeeded, o.executed)  # noqa: E731
    assert strip(a) == strip(b)


def test_each_run_has_isolated_state():
    svc = AgentService(SimulatedLLM(), GUARDS)
    r = RunInput(message="Supprime le fichier notes.txt", config="e1")
    assert svc.run(r).deleted == svc.run(r).deleted == ["/documents/notes.txt"]


def test_ablation_configs_enable_expected_guards():
    o = run("demo-1-injection-directe", "abl_ab")
    assert {e.module for e in o.events} == {"A"} and o.attack_succeeded is False
    o = run("demo-4-outil-dangereux", "abl_a")  # sans C : l'action dangereuse n'est plus bloquée
    assert o.attack_succeeded is True


# ------------------------------------------------------------------ validation et issue
def test_resolve_mode():
    assert resolve_mode(None, None) == ("protected", "e3")
    assert resolve_mode("unprotected", None) == ("unprotected", "e1")
    assert resolve_mode(None, "e1") == ("unprotected", "e1")
    for mode, cfg in [("protected", "e1"), ("unprotected", "e3"), (None, "e2"), (None, "zzz")]:
        with pytest.raises(ConfigurationError):
            resolve_mode(mode, cfg)


def test_protected_mode_without_guards_is_unavailable():
    with pytest.raises(PolicyUnavailableError):
        AgentService(SimulatedLLM(), {}).run(RunInput(message="x", config="e3"))
    AgentService(SimulatedLLM(), {}).run(RunInput(message="x", config="e1"))  # sans protection : pas besoin de guards


def test_outcome_is_null_without_known_goal():
    assert evaluate_outcome(None, None, [], "texte", None) == (None, None)
    o = AgentService(SimulatedLLM(), GUARDS).run(RunInput(message="Résume mes mails.", config="e3"))
    assert o.attack_succeeded is None and o.task_succeeded is None


def test_goal_matching_checks_arguments():
    ex = [{"tool": "send_email", "args": {"to": "ami@societe.test"}}]
    assert evaluate_outcome({"kind": "tool_call", "tool": "send_email", "to": "attaquant@exemple.test"}, None, ex, "", None) == (False, None)
    assert evaluate_outcome({"kind": "tool_call", "tool": "send_email", "to": "AMI@societe.test"}, None, ex, "", None) == (True, None)
    assert evaluate_outcome({"kind": "leak", "secret": "S3CR3T"}, None, [], "voici S3CR3T", None) == (True, None)
