"""AS-S1-024 : les fixtures du mock du Lab doivent refléter le comportement ACTUEL de l'agent (régénération = fichier versionné).

Si ce test échoue après une évolution du service IA : `python scripts/gen_lab_mocks.py` puis relire le diff de
`frontend/src/mocks/simulation.fixtures.ts` (les données de démonstration ne doivent jamais diverger de l'agent réel).
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_lab_fixtures_match_the_real_agent():
    spec = importlib.util.spec_from_file_location("gen_lab_mocks", ROOT / "scripts" / "gen_lab_mocks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    committed = (ROOT / "frontend" / "src" / "mocks" / "simulation.fixtures.ts").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert module.render() == committed
