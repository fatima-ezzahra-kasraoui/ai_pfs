import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "scan_secrets.py"
spec = importlib.util.spec_from_file_location("scan_secrets", SCRIPT)
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)

FAKE_REAL_LOOKING = "sk-" + "A1b2C3d4E5f6G7h8I9j0K1l2"  # assemblé à l'exécution pour ne pas committer un faux secret


def test_planted_secret_is_detected_and_fails(tmp_path):
    f = tmp_path / "config.py"
    f.write_text(f'API = "{FAKE_REAL_LOOKING}"\n')
    r = subprocess.run([sys.executable, str(SCRIPT), str(f)], capture_output=True, text=True)
    assert r.returncode == 1 and "SECRET" in r.stdout
    assert FAKE_REAL_LOOKING not in r.stdout  # le secret n'est jamais réaffiché


def test_documented_canary_is_allowed(tmp_path):
    f = tmp_path / "ok.txt"
    f.write_text("canary: sk-FAKE-1234\n")
    assert subprocess.run([sys.executable, str(SCRIPT), str(f)], capture_output=True).returncode == 0


def test_patterns():
    assert scan.scan_text("AKIA" + "ABCDEFGHIJKLMNOP")
    assert scan.scan_text("-----BEGIN RSA PRIVATE KEY-----")
    assert scan.scan_text('password = "SuperSecret123"')
    assert not scan.scan_text('password = "change-me"')
    assert not scan.scan_text("rien à signaler")


def test_repository_is_clean():
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout


def test_no_raw_secret_in_audit_samples_or_results():
    """Aucun faux secret « réel » ne doit figurer dans les résultats produits (NF01)."""
    for path in (ROOT / "ai-service" / "evaluation" / "results").glob("*.json"):
        assert not scan.scan_text(path.read_text(encoding="utf-8")), path.name
