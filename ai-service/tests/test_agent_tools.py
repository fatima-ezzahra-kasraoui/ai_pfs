"""AS-S1-021 : les cinq outils factices (comportements, validation, aucune opération réelle)."""
import os

import pytest

from app.agent.tools import CANARY_SECRET, TOOL_NAMES, ToolBox, ToolError, normalize_path, tool_specs


def test_exactly_the_five_policy_tools():
    import yaml

    from app.core.config import POLICY_PATH

    policy_tools = set(yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))["tools"])
    assert set(TOOL_NAMES) == policy_tools == {"read_email", "browse_web", "read_file", "send_email", "delete_file"}
    assert [s.name for s in tool_specs()] == list(TOOL_NAMES)
    for spec in tool_specs():
        assert spec.parameters["type"] == "object" and spec.description


def test_read_email_all_and_by_id():
    box = ToolBox()
    assert len(box.execute("read_email", {}).output["emails"]) == 2
    one = box.execute("read_email", {"email_id": "mail-1"})
    assert "compte rendu" in one.text and one.external_content
    with pytest.raises(ToolError):
        box.execute("read_email", {"email_id": "inconnu"})


def test_read_file_and_missing_file():
    box = ToolBox()
    assert CANARY_SECRET in box.execute("read_file", {"path": "/documents/config.txt"}).text
    assert box.execute("read_file", {"path": "documents\\notes.txt"}).output["path"] == "/documents/notes.txt"
    with pytest.raises(ToolError):
        box.execute("read_file", {"path": "/documents/absent.txt"})


@pytest.mark.parametrize("bad", ["../etc/passwd", "/documents/../../etc/passwd", "a\x00b", "..\\x"])
def test_path_traversal_rejected(bad):
    with pytest.raises(ToolError):
        normalize_path(bad)
    with pytest.raises(ToolError):
        ToolBox().execute("read_file", {"path": bad})


def test_real_filesystem_is_never_touched(tmp_path):
    victim = tmp_path / "vrai.txt"
    victim.write_text("x")
    box = ToolBox()
    with pytest.raises(ToolError):
        box.execute("delete_file", {"path": str(victim)})
    assert victim.exists()
    with pytest.raises(ToolError):
        box.execute("read_file", {"path": str(victim)})
    assert os.path.exists(victim)


def test_delete_file_is_simulated_and_per_run():
    box = ToolBox()
    r = box.execute("delete_file", {"path": "/documents/rapport_final.docx"})
    assert r.output["status"] == "simulated_deleted" and r.simulated and "aucune suppression réelle" in r.side_effect
    assert "/documents/rapport_final.docx" not in box.files and box.deleted == ["/documents/rapport_final.docx"]
    with pytest.raises(ToolError):
        box.execute("delete_file", {"path": "/documents/rapport_final.docx"})  # déjà supprimé
    assert "/documents/rapport_final.docx" in ToolBox().files  # exécution suivante : état d'origine


def test_send_email_is_recorded_not_sent():
    box = ToolBox()
    r = box.execute("send_email", {"to": "bob@societe.test", "subject": "Hello", "body": "Salut"})
    assert r.output["status"] == "simulated_sent" and box.outbox == [{"id": "sim-1", "to": "bob@societe.test", "subject": "Hello", "body": "Salut"}]
    assert box.execute("send_email", {"to": "c@societe.test"}).output["messageId"] == "sim-2"


@pytest.mark.parametrize("bad", ["pas-une-adresse", "a@b", "a b@c.test", "x@y.test, z@w.test", "<a@b.test>"])
def test_send_email_rejects_invalid_address(bad):
    with pytest.raises(ToolError):
        ToolBox().execute("send_email", {"to": bad})


def test_browse_web_known_unknown_and_scheme():
    box = ToolBox()
    assert "intranet" in box.execute("browse_web", {"url": "https://intranet.societe.test/actualites/"}).text
    with pytest.raises(ToolError):
        box.execute("browse_web", {"url": "https://exemple.org"})
    with pytest.raises(ToolError):
        box.execute("browse_web", {"url": "file:///etc/passwd"})


def test_unknown_tool_and_invalid_arguments():
    box = ToolBox()
    with pytest.raises(ToolError, match="outil inconnu"):
        box.execute("execute_shell", {"cmd": "rm -rf /"})
    with pytest.raises(ToolError, match="invalides"):
        box.execute("read_file", {})
    with pytest.raises(ToolError, match="invalides"):
        box.execute("read_file", {"path": "/a", "extra": 1})  # champ inconnu refusé


def test_fixture_overrides_only_the_named_tool():
    box = ToolBox(fixture={"name": "read_email", "content": "<!-- piège -->"})
    assert "<!-- piège -->" in box.execute("read_email", {}).text
    assert CANARY_SECRET in box.execute("read_file", {"path": "/documents/config.txt"}).text  # autre outil : inchangé
    file_box = ToolBox(fixture={"name": "read_file", "content": "contenu imposé"})
    assert file_box.execute("read_file", {"path": "/n/importe/quoi"}).text == "contenu imposé"


def test_state_is_isolated_between_toolboxes():
    a, b = ToolBox(), ToolBox()
    a.execute("send_email", {"to": "x@societe.test"})
    assert b.outbox == [] and a.emails is not b.emails
