"""AS-S2-007 : chargement, validation et rechargement à chaud de policy.yaml."""
import os
import textwrap
import threading
import time
from pathlib import Path

import pytest
import yaml

from app.core.config import POLICY_PATH
from app.core.policy import Policy, PolicyError, PolicyStore, load_policy, parse_policy

VALID = textwrap.dedent(
    """
    thresholds: { injection_block: 0.90, injection_review: 0.50, coherence_min: 0.40 }
    tools:
      read_file: { risk: low, allowed: true }
      send_email: { risk: medium, allowed: true, confirm_if_unknown_recipient: true }
    output:
      mask_patterns: [api_key]
      canary_tokens: [sk-FAKE-1234]
      on_secret_detected: SANITIZE
      on_canary_in_outgoing_tool: BLOCK
    """
)


def write(tmp_path: Path, text: str = VALID, name: str = "policy.yaml") -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def mutated(**changes) -> str:
    data = yaml.safe_load(VALID)
    for dotted, value in changes.items():
        node = data
        *path, last = dotted.split(".")
        for key in path:
            node = node[key]
        if value is None:
            del node[last]
        else:
            node[last] = value
    return yaml.safe_dump(data)


# ------------------------------------------------------------------ fichier du dépôt
def test_repository_policy_is_valid():
    policy = load_policy(POLICY_PATH)
    assert isinstance(policy, Policy)
    assert (policy.thresholds.injection_block, policy.thresholds.injection_review, policy.thresholds.coherence_min) == (0.9, 0.5, 0.4)


def test_repository_policy_has_no_db_path():
    assert "db_path" not in POLICY_PATH.read_text(encoding="utf-8")
    assert "db_path" not in yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))["logging"]


def test_repository_policy_tools_match_the_five_fake_tools():
    from app.agent.tools import PARAMS, TOOL_NAMES

    policy = load_policy(POLICY_PATH)
    assert set(policy.tools) == set(TOOL_NAMES)
    for name, model in PARAMS.items():
        assert set(policy.tools[name].allowed_params or ()) == set(model.model_fields), name  # liste blanche de paramètres = signature réelle


def test_repository_policy_matches_what_other_modules_read():
    """Compatibilité avec les lecteurs de Fati : seuils d'évaluation, Guard D."""
    from app.guards.output_guard import OutputGuard
    from evaluation.guard_eval import load_thresholds

    th = load_thresholds(POLICY_PATH)
    assert th["injection_block"] == 0.9 and th["injection_review"] == 0.5
    guard = OutputGuard.from_policy(POLICY_PATH)
    assert guard.check({"text": "API_KEY=sk-FAKE-1234", "channel": "final_response"}).metadata["canary"] is True


def test_tune_thresholds_rewrite_keeps_the_policy_valid(tmp_path):
    """L'outil de réglage de Fati réécrit les seuils par expression régulière : le fichier doit rester valide."""
    import re

    text = POLICY_PATH.read_text(encoding="utf-8")
    text = re.sub(r"(^\s*injection_block:\s*)[0-9.]+", r"\g<1>0.85", text, flags=re.M)
    text = re.sub(r"(^\s*injection_review:\s*)[0-9.]+", r"\g<1>0.45", text, flags=re.M)
    policy = load_policy(write(tmp_path, text))
    assert (policy.thresholds.injection_block, policy.thresholds.injection_review) == (0.85, 0.45)


# ------------------------------------------------------------------ validation
def test_minimal_annex_a_policy_is_valid_and_gets_safe_defaults():
    policy = parse_policy(VALID)
    assert policy.thresholds.coherence_min_lexical == 0.10
    assert policy.decisions.on_incoherent_after_indirect_injection == "BLOCK"
    assert policy.decisions.review_action.input == "CONFIRM" and policy.logging.mask_excerpts is True
    assert policy.tool("send_email").confirm_if_unknown_recipient and policy.tool("inconnu") is None


@pytest.mark.parametrize(
    "changes,fragment",
    [
        ({"thresholds.injection_block": 1.5}, "thresholds.injection_block"),
        ({"thresholds.injection_review": -0.1}, "thresholds.injection_review"),
        ({"thresholds.injection_review": 0.95}, "injection_review doit être inférieur"),
        ({"thresholds.coherence_min": "beaucoup"}, "thresholds.coherence_min"),
        ({"thresholds.injection_block": None}, "thresholds.injection_block"),
        ({"tools.read_file.risk": "critical"}, "tools.read_file.risk"),
        ({"tools.read_file.allowed": "peut-être"}, "tools.read_file.allowed"),
        ({"tools.read_file.inconnu": True}, "tools.read_file.inconnu"),
        ({"output.on_secret_detected": "ALLOW"}, "output.on_secret_detected"),
        ({"output.on_canary_in_outgoing_tool": "SANITIZE"}, "output.on_canary_in_outgoing_tool"),
        ({"output.canary_tokens": [" "]}, "canary token"),
        ({"output": None}, "output"),
        ({"tools": None}, "tools"),
        ({"clef_inconnue": 1}, "clef_inconnue"),
        ({"decisions.on_sensitive_path": "ALLOW"}, "decisions.on_sensitive_path"),
        ({"decisions.review_action.final_response": "CONFIRM"}, "CONFIRM n'est possible que pour un message"),
        ({"decisions.review_action.tool_result": "CONFIRM"}, "CONFIRM n'est possible que pour un message"),
        ({"decisions.review_action.input": "ALLOW"}, "ALLOW n'a pas de sens"),
    ],
)
def test_invalid_policy_is_rejected_with_a_clear_error(tmp_path, changes, fragment):
    text = mutated(**{k: v for k, v in changes.items() if not k.startswith("decisions")})
    if any(k.startswith("decisions") for k in changes):
        data = yaml.safe_load(text)
        for dotted, value in changes.items():
            node = data
            *path, last = dotted.split(".")
            for key in path:
                node = node.setdefault(key, {})
            node[last] = value
        text = yaml.safe_dump(data)
    with pytest.raises(PolicyError) as exc:
        load_policy(write(tmp_path, text))
    assert fragment in str(exc.value) and "policy.yaml" in str(exc.value)


def test_removed_db_path_key_is_rejected_with_explanation(tmp_path):
    with pytest.raises(PolicyError, match="logging.db_path a été retirée"):
        load_policy(write(tmp_path, mutated(**{"logging": {"db_path": "x.db", "mask_excerpts": True}})))


@pytest.mark.parametrize("text", ["", "- une\n- liste", "42", "thresholds: [", "{{{pas du yaml"])
def test_non_mapping_or_broken_yaml_is_rejected(tmp_path, text):
    with pytest.raises(PolicyError):
        load_policy(write(tmp_path, text))


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(PolicyError, match="illisible"):
        load_policy(tmp_path / "absent.yaml")
    with pytest.raises(PolicyError):
        PolicyStore(tmp_path / "absent.yaml")


def test_error_messages_never_contain_values_of_the_file(tmp_path):
    with pytest.raises(PolicyError) as exc:
        load_policy(write(tmp_path, mutated(**{"output.canary_tokens": "sk-SECRET-A-NE-PAS-AFFICHER"})))
    assert "sk-SECRET-A-NE-PAS-AFFICHER" not in str(exc.value)


def test_policy_is_immutable():
    policy = parse_policy(VALID)
    with pytest.raises(Exception):  # noqa: B017 - ValidationError de Pydantic (modèle gelé)
        policy.thresholds.injection_block = 0.1  # type: ignore[misc]


def test_parameters_are_normalised_to_lowercase():
    policy = parse_policy(mutated(parameters={"known_recipient_domains": ["Societe.TEST"], "sensitive_paths": ["*/.ENV"]}))
    assert policy.parameters.known_recipient_domains == ("societe.test",) and policy.parameters.sensitive_paths == ("*/.env",)


# ------------------------------------------------------------------ rechargement sans redémarrage
def bump(path: Path) -> None:
    """Garantit un changement de signature (mtime) même sur un système de fichiers à granularité grossière."""
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))


def test_changed_threshold_is_taken_into_account_without_restart(tmp_path):
    path = write(tmp_path)
    store = PolicyStore(path)
    assert store.get().thresholds.injection_block == 0.9
    path.write_text(mutated(**{"thresholds.injection_block": 0.8}), encoding="utf-8")
    bump(path)
    assert store.get().thresholds.injection_block == 0.8
    assert store.last_error is None


def test_digest_changes_with_content(tmp_path):
    path = write(tmp_path)
    store = PolicyStore(path)
    before = store.digest
    path.write_text(mutated(**{"thresholds.coherence_min": 0.45}), encoding="utf-8")
    bump(path)
    store.get()
    assert store.digest != before and len(store.digest) == 64


def test_invalid_reload_keeps_the_previous_valid_policy(tmp_path):
    path = write(tmp_path)
    store = PolicyStore(path)
    path.write_text(mutated(**{"thresholds.injection_block": 7}), encoding="utf-8")
    bump(path)
    assert store.get().thresholds.injection_block == 0.9  # jamais de politique invalide ni permissive
    assert "thresholds.injection_block" in store.last_error
    path.write_text(mutated(**{"thresholds.injection_block": 0.7}), encoding="utf-8")
    bump(path)
    assert store.get().thresholds.injection_block == 0.7 and store.last_error is None  # reprise dès que le fichier est corrigé


def test_deleted_file_keeps_the_previous_policy(tmp_path):
    path = write(tmp_path)
    store = PolicyStore(path)
    path.unlink()
    assert store.get().thresholds.injection_block == 0.9 and "illisible" in store.last_error


def test_explicit_reload_raises_but_keeps_previous_policy(tmp_path):
    path = write(tmp_path)
    store = PolicyStore(path, auto_reload=False)
    path.write_text("n'importe quoi", encoding="utf-8")
    with pytest.raises(PolicyError):
        store.reload()
    assert store.get().thresholds.injection_block == 0.9
    assert store.reload(raise_on_error=False).thresholds.injection_block == 0.9


def test_auto_reload_can_be_disabled(tmp_path):
    path = write(tmp_path)
    store = PolicyStore(path, auto_reload=False)
    path.write_text(mutated(**{"thresholds.injection_block": 0.8}), encoding="utf-8")
    bump(path)
    assert store.get().thresholds.injection_block == 0.9
    assert store.reload().thresholds.injection_block == 0.8


def test_invalid_file_is_not_reparsed_in_a_loop(tmp_path, monkeypatch):
    path = write(tmp_path)
    store = PolicyStore(path)
    path.write_text("invalide", encoding="utf-8")
    bump(path)
    store.get()
    calls = []
    monkeypatch.setattr("app.core.policy.parse_policy", lambda *a, **k: calls.append(1) or (_ for _ in ()).throw(PolicyError("x")))
    for _ in range(5):
        store.get()
    assert calls == []  # fichier inchangé : pas de relecture


def test_concurrent_readers_always_see_a_complete_valid_policy(tmp_path):
    path = write(tmp_path)
    store = PolicyStore(path)
    seen, errors = set(), []

    def reader():
        for _ in range(200):
            try:
                seen.add(store.get().thresholds.injection_block)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

    threads = [threading.Thread(target=reader) for _ in range(4)]
    for t in threads:
        t.start()
    for value in (0.8, 0.7, 0.9, 0.6):
        path.write_text(mutated(**{"thresholds.injection_block": value}), encoding="utf-8")
        bump(path)
        time.sleep(0.01)
    for t in threads:
        t.join()
    assert errors == [] and seen <= {0.9, 0.8, 0.7, 0.6}
