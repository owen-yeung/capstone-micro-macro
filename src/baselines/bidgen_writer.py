"""Experiment 7: dedicated construction technical-proposal writer."""
from __future__ import annotations

IMPLEMENTED = False
VENDOR = "vendor/baselines/claude-bid-gen"
ENGINE = "bidgen"


def write_bid_document(*_args, **_kwargs):
    raise NotImplementedError(
        "Bid-document writer swap is specified, not yet wired. "
        f"Clone {VENDOR} and implement src/baselines/bidgen_writer.py. "
        "Who may submit remains OrgBid's participation and consortium outcome."
    )
