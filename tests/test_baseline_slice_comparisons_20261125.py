"""Offline checks for the stage-isolated baseline comparison harness."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from src.baselines.award_topsis import compare_package, kendall_tau, rank_package
from src.baselines.contracts import assert_no_hidden_labels
from src.models import BidDocument, Company, EvaluationReport, OpeningRecord, SimulationState, TenderPackage

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_baseline_slice_comparisons_20261125.py"
EXP = ROOT / "results/experiments/baseline_slice_comparisons_20261125"


def _load():
    spec = importlib.util.spec_from_file_location("baseline_slice_20261125", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _bid(bidder_id: str, price: float, days: str, risk: int, name: str = "") -> BidDocument:
    return BidDocument(
        bid_id=f"bid-{bidder_id}",
        package_id="pkg-1",
        bidder_type="contractor",
        bidder_id=bidder_id,
        bidder_name=name or bidder_id,
        technical_proposal="method",
        implementation_plan="plan",
        quotation=price,
        schedule_commitment=days,
        compliance_statement="yes",
        risk_response="risks listed",
        submission_summary="summary",
        unresolved_condition_ids=[f"c{i}" for i in range(risk)],
    )


def _state() -> SimulationState:
    companies = [
        Company("A", "Firm A", "contractor", "profile", ["piling"], [], ["qual-a", "qual-b"], ["job"], "large", [], ["pkg-1"]),
        Company("B", "Firm B", "contractor", "profile", [], ["thin staff"], ["qual-b"], [], "small", ["delay"], ["pkg-1"]),
        Company("C", "Firm C", "contractor", "profile", ["steel"], [], ["qual-c"], ["job", "job2"], "medium", [], ["pkg-1"]),
    ]
    bids = [
        _bid("A", 100, "200 days", 0, "Firm A"),
        _bid("B", 80, "400 days", 3, "Firm B"),
        _bid("C", 120, "180 days", 1, "Firm C"),
    ]
    return SimulationState(
        companies=companies,
        tender_packages=[TenderPackage("pkg-1", "works", "Main works", "scope", "contractor", [], [], "lump", [], "award")],
        bid_documents=bids,
        opening_record=[OpeningRecord("pkg-1", [{"bidder_id": "A"}, {"bidder_id": "B"}, {"bidder_id": "C"}], "3 opened")],
        evaluation_report=[EvaluationReport("pkg-1", ["owner"], [{"bidder_id": "A"}, {"bidder_id": "C"}, {"bidder_id": "B"}], "org", "A", "notes")],
    )


def test_topsis_prefers_cheaper_capable_bid_over_risky_low_price():
    ranked = rank_package(_state(), "pkg-1")
    assert [item.bidder_id for item in ranked][0] in {"A", "C"}
    assert "B" in {item.bidder_id for item in ranked}


def test_empty_opened_set_is_no_award():
    state = _state()
    state.opening_record = [OpeningRecord("pkg-1", [], "none")]
    comparison = compare_package(state, "pkg-1")
    assert comparison["numerical_winner"] is None
    assert comparison["n_admissible"] == 0


def test_kendall_tau_identical_and_reversed():
    assert kendall_tau(["A", "B", "C"], ["A", "B", "C"]) == 1.0
    assert kendall_tau(["A", "B", "C"], ["C", "B", "A"]) == -1.0


def test_hidden_labels_are_rejected():
    try:
        assert_no_hidden_labels({"bids": [{"matched_enterprise_name": "secret"}]})
    except ValueError as exc:
        assert "matched_enterprise_name" in str(exc)
    else:
        raise AssertionError("hidden field must be rejected")


def test_live_refuses_without_authorization():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "run", "--slice", "award", "--engine", "topsis"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Refusing live calls" in (result.stderr + result.stdout)


def test_protocol_shape():
    protocol = json.loads((EXP / "protocol.json").read_text(encoding="utf-8"))
    assert protocol["experiment_id"] == "baseline_slice_comparisons_20261125"
    assert protocol["design"]["hidden_labels_withheld_from_engines"] is True
    assert protocol["n_jobs"] == len(protocol["jobs"])
    assert {job["case_id"] for job in protocol["jobs"]} >= {"CASE-0014", "CASE-0089", "CASE-0253"}


def test_prepare_is_idempotent():
    first = subprocess.run([sys.executable, str(SCRIPT), "prepare"], cwd=ROOT, capture_output=True, text=True)
    second = subprocess.run([sys.executable, str(SCRIPT), "prepare"], cwd=ROOT, capture_output=True, text=True)
    assert first.returncode == 0
    assert second.returncode == 0
