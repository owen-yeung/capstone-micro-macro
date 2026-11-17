from math import isclose
from pathlib import Path

from src.ablation import AblationConfig
from src.discussion_participants import round_participants
from src.models import MemberAgent
from src.stage_memory import company_package_memory
from src.tender_metrics.size_matched_baseline import (
    aggregate_package_scores,
    score_archived_28_cases,
    size_matched_hit_probability,
)

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "validation/benchmark_ge3_compact/results/final_28_20260817/cases"
BENCH = ROOT / "validation/benchmark_ge3_compact/data/hidden_benchmark_project_enterprises.csv"


def test_formula_six_examples():
    assert isclose(size_matched_hit_probability(3, 1, 1), 1 / 3)
    assert isclose(size_matched_hit_probability(4, 2, 2), 1 - (1 / 6))
    assert size_matched_hit_probability(5, 0, 2) == 0.0
    assert size_matched_hit_probability(5, 4, 2) == 1.0


def test_frozen_28_matches_interim_published_rates():
    packages = score_archived_28_cases(CASES, BENCH)
    summary = aggregate_package_scores(packages)
    overall = summary["overall"]
    assert overall["hits"] == 46
    assert overall["denominator"] == 71
    assert isclose(overall["hit_rate"], 46 / 71, rel_tol=0, abs_tol=1e-12)
    assert isclose(overall["mean_size_matched_baseline"], 0.576, rel_tol=0, abs_tol=5e-4)
    by_role = summary["by_role"]
    assert isclose(by_role["designer"]["hit_rate"], 0.810, abs_tol=5e-4)
    assert isclose(by_role["designer"]["mean_size_matched_baseline"], 0.651, abs_tol=5e-4)
    assert isclose(by_role["contractor"]["hit_rate"], 0.538, abs_tol=5e-4)
    assert isclose(by_role["contractor"]["mean_size_matched_baseline"], 0.522, abs_tol=5e-4)
    assert isclose(by_role["supervisor"]["hit_rate"], 0.682, abs_tol=5e-4)
    assert isclose(by_role["supervisor"]["mean_size_matched_baseline"], 0.591, abs_tol=5e-4)


def test_ablation_a1_uses_only_final_agent():
    agents = [
        MemberAgent("a1", "A", "c1", "designer", "Tech", "Engineer", "p", ["r"], "review", "direct"),
        MemberAgent("a2", "B", "c1", "designer", "Mgmt", "GM", "p", ["r"], "final", "direct"),
    ]
    participants = round_participants(agents, "full", False, single_agent_firm=True)
    assert [agent.agent_id for agent in participants] == ["a2"]


def test_ablation_config_ids():
    assert AblationConfig.from_id("A3").active_ids() == ["A3"]
    assert AblationConfig.from_id("none").active_ids() == []


def test_a4_memory_disabled():
    class Msg:
        def __init__(self):
            self.company_id = "c1"
            self.package_id = "design_package"
            self.stage = "bid_participation_decision"

    class State:
        agent_discussion_history = [Msg()]

    assert len(company_package_memory(State(), "c1", "design_package")) == 1
    assert company_package_memory(State(), "c1", "design_package", disabled=True) == []
