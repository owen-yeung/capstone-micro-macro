# Interim §6.2 offline deliverables (2026-11-17)

Implements the offline-ready next steps from the Capstone interim report §6.2 without new model calls.

| Artifact | Path | Notes |
|---|---|---|
| Size-matched hit@1 report | `size_matched_hit28/` | Reproduces 46/71 = 64.8% vs 57.6% baseline |
| Human BP rubric packets | `human_eval_packets/` | 24 blinded blanks; ratings not filled |
| Price/duration field audit | `price_duration_field_audit/` | Validation blocked pending field confirmation |
| 352 expansion eligibility | `full_352_eligibility/` | Inputs ready; tender runs not executed |

Protocol index: `research/interim_6_2_protocols.md`.

Ablation CLI flags A1–A4 are in `main.py --ablation`; authorized LLM arms are still gated.
