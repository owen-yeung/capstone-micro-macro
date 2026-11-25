"""Experiment 5a: language-model negotiation floor (Abdelnabi-style).

Not implemented in this commit. The PIC live runner will refuse this engine
until `IMPLEMENTED` is True and the vendor checkout is present. See
research/references/baseline_comparison_implementation_spec.md §5.
"""
from __future__ import annotations

IMPLEMENTED = False
VENDOR = "vendor/baselines/llm-deliberation"
ENGINE = "llm_delib"


def run_floor(*_args, **_kwargs):
    raise NotImplementedError(
        "Consortium language-model floor is specified, not yet wired. "
        f"Clone {VENDOR} and implement src/baselines/consortium_llm_delib.py "
        "(keep intra-firm rounds 1–3 and reconsideration as OrgBid)."
    )
