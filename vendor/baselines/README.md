# External comparison engines (not committed)

Clone the third-party trees here locally. Do **not** commit the checkouts, virtualenvs, or model weights. They are large, licensed separately, and are not OrgBid evidence.

| Directory | Source | Used by |
|---|---|---|
| `llm-deliberation/` | https://github.com/S-Abdelnabi/LLM-Deliberation | Experiment 5 language-model floor |
| `MARBLE/` | https://github.com/ulab-uiuc/MARBLE | Experiment 6 communication structures |
| `claude-bid-gen/` | https://github.com/tiettuo/claude-bid-gen | Experiment 7 bid-document writer |

`negmas` and `pymcdm` are pip extras, not clones. See `research/references/baseline_comparison_implementation_spec.md`.

After cloning, pin the commit SHA in `runs/baseline_slice_comparisons_20261125/vendor_pins.json` (gitignored) and copy that file into the frozen `full_run.zip`.
