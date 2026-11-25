"""Stage-isolated external comparison adapters.

Each adapter replaces one tendering act and writes OrgBid types back. Hidden
historical partners, contract values, and durations must never enter engine
inputs; see `src.baselines.contracts.assert_no_hidden_labels`.
"""

IMPLEMENTED_ENGINES = {"topsis", "weighted_sum"}
PLANNED_ENGINES = {
    "llm_delib": "src.baselines.consortium_llm_delib",
    "negmas": "src.baselines.consortium_negmas",
    "marble_star": "src.baselines.intra_marble",
    "marble_chain": "src.baselines.intra_marble",
    "marble_graph": "src.baselines.intra_marble",
    "bidgen": "src.baselines.bidgen_writer",
}
