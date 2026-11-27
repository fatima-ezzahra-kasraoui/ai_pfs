import pytest

from app.agent import real_tools as r
from app.agent.tools import ToolError


def test_real_file(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "ROOT", tmp_path)
    (tmp_path / "demo.txt").write_text("real content")
    box = r.RealToolBox()
    result = box.execute("read_file", {"path": "demo.txt"})
    assert result.text == "real content" and not result.simulated
    assert "demo.txt" in box.execute("read_file", {"path": "list"}).text
    for path in ("../demo.txt", "/etc/passwd", "missing.txt"):
        with pytest.raises(ToolError):
            box.execute("read_file", {"path": path})
    with pytest.raises(ToolError):
        box.execute("delete_file", {"path": "demo.txt"})
    assert (tmp_path / "demo.txt").exists()


def test_web_reject():
    with pytest.raises(ToolError):
        r.RealToolBox().execute("browse_web", {"url": "http://127.0.0.1/"})


def test_recipient_reject():
    with pytest.raises(ToolError):
        r.RealToolBox().execute("send_email", {"to": "other@example.com"})


def test_symlink(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "ROOT", tmp_path)
    (tmp_path / "link.txt").symlink_to("/etc/passwd")
    with pytest.raises(ToolError):
        r.RealToolBox().execute("read_file", {"path": "link.txt"})
