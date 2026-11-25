"""Experiment 6: generic communication structures on bid/no-bid tasks."""
from __future__ import annotations

IMPLEMENTED = False
VENDOR = "vendor/baselines/MARBLE"
ENGINES = ("marble_star", "marble_chain", "marble_graph")


def run_discussion(*_args, **_kwargs):
    raise NotImplementedError(
        "Intra-firm MARBLE communication structures are specified, not yet wired. "
        f"Clone {VENDOR} and implement src/baselines/intra_marble.py. "
        "Only the decision-holding member may write ParticipationDecision."
    )
