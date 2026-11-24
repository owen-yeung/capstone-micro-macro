"""Offline checks for the external dialogue PIC package."""
import argparse
from pathlib import Path

from scripts.run_external_dialogue_generation_20261125 import (
    AWARD_PACKET,
    GAME_DIR,
    PACKAGE,
    ROOT,
    RUNS,
    cmd_dry_run,
    cmd_prepare,
    load_agents,
    load_protocol,
    materialize_requests,
    parse_deal_codes,
    score_deal,
)


def test_package_inputs_exist():
    assert (PACKAGE / "README.md").is_file()
    assert (GAME_DIR / "global_instructions.txt").is_file()
    assert (GAME_DIR / "config.txt").is_file()
    assert AWARD_PACKET.is_file()


def test_parse_and_score_deal_from_game_scores():
    agents = load_agents(GAME_DIR)
    deal = parse_deal_codes("We agree on A1,B1", issues_num=2, agents_num=3)
    assert deal == ["A1", "B1"]
    scored = score_deal(deal, agents, GAME_DIR)
    # A1/B1 assigns both issues to COMP-0199 (first agent); that firm scores 10+10.
    assert scored["utility"]["COMP-0199"] == 20
    assert scored["agreement_success"] is True


def test_prepare_and_dry_run_materialize_requests():
    cmd_prepare(argparse.Namespace(model="deepseek-flash"))
    protocol = load_protocol()
    assert protocol["planned_calls"] == sum(arm["calls"] for arm in protocol["arms"])
    assert protocol["planned_calls"] >= 20
    ledger = materialize_requests(protocol)
    assert len(ledger) == protocol["planned_calls"]
    assert (ROOT / ledger[0]["request"]).is_file()
    cmd_dry_run(argparse.Namespace())
    assert (RUNS / "dry_run_ledger.json").is_file()
    assert Path(ROOT / "results/experiments/external_dialogue_generation_20261125/protocol.json").is_file()
