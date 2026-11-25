"""Experiment 5b: classical automated negotiation over the same four issues."""
from __future__ import annotations

IMPLEMENTED = False
VENDOR = "pip extra baselines-negotiate (negmas)"
ENGINE = "negmas"


def run_floor(*_args, **_kwargs):
    raise NotImplementedError(
        "Classical automated negotiation floor is specified, not yet wired. "
        "Install negmas via pip extra baselines-negotiate and implement "
        "src/baselines/consortium_negmas.py."
    )
