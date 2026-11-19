"""Smoke checks for offline org-deliberation metrics helpers."""
from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_org_deliberation_metrics_20261119.py"


def _load():
    spec = importlib.util.spec_from_file_location("org_metrics_20261119", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_info_and_base_helpers():
    m = _load()
    assert m.info_of("CP00-EXPAND-01-full") == "full"
    assert m.info_of("CP00-EXPAND-01-missing_core") == "missing_core"
    assert m.base_of("CP00-EXPAND-01-missing_core") == "CP00-EXPAND-01"
    assert m.base_of("CP00-EXPAND-01-full") == "CP00-EXPAND-01"


def test_project_equal_delta_aggregates():
    m = _load()
    rows = [
        {"project_group": "p1", "role": "supplier", "D2__D3": 1.0, "D2__S4": 0.8},
        {"project_group": "p1", "role": "supplier", "D2__D3": 0.8, "D2__S4": 0.8},
        {"project_group": "p2", "role": "contractor", "D2__D3": 0.5, "D2__S4": 0.7},
    ]
    out = m.project_equal_delta(rows, "D3", "S4", "D2")
    assert out["n_projects"] == 2
    # p1 mean delta = 0.1; p2 = -0.2; overall mean = -0.05
    assert abs(out["project_mean_delta"] - (-0.05)) < 1e-9


def test_frozen_artifacts_present():
    out = ROOT / "results/experiments/org_deliberation_metrics_20261119"
    assert (out / "summary.json").exists()
    assert (out / "SUMMARY.md").exists()
    assert (out / "scores" / "subset_llm_scores.json").exists()
    scores = __import__("json").loads((out / "scores" / "subset_llm_scores.json").read_text(encoding="utf-8"))
    assert len(scores["windows"]) == 12
    assert scores["scoring_protocol"]["new_model_calls"] == 0
