"""Smoke checks for org ablation sensitivity prepare/dry-run helpers."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_org_ablation_sensitivity_20261119.py"
EXP = ROOT / "results/experiments/org_ablation_sensitivity_20261119"


def _load():
    spec = importlib.util.spec_from_file_location("org_ablation_20261119", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_protocol_frozen_shape():
    protocol = json.loads((EXP / "protocol.json").read_text(encoding="utf-8"))
    assert protocol["seed_string"] == "org-ablation-20261119"
    assert protocol["max_calls"] == 56
    assert len(protocol["windows"]) == 8
    assert len(protocol["jobs"]) == 56
    roles = {w["role"] for w in protocol["windows"]}
    assert roles == {"contractor", "supplier", "designer", "supervisor"}


def test_live_refuses_without_authorization():
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "run", "--max-calls", "1"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0
    assert "Refusing live calls" in (r.stderr + r.stdout)


def test_dropout_builder_removes_one_proposal():
    m = _load()
    protocol = json.loads((EXP / "protocol.json").read_text(encoding="utf-8"))
    window = protocol["windows"][0]
    req = m.build_ablation_request(window, "dropout_step1")
    idx, props = m.extract_internal_proposals(req["messages"])
    assert len(props) == 2
    assert req["ablation"]["kind"] == "dropout_step1"
