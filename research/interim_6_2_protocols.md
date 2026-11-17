# Interim §6.2 next-step protocols (offline-ready)

Source: `research/references/submitted_interim.pdf` §5.5–§6.2.  
These protocols implement the remaining next steps without launching paid model calls. Real LLM execution still needs a fresh authorized task scope (`AGENTS.md`).

## Already executable offline

| Item | Entry | Status |
|---|---|---|
| Size-matched baseline as standard report | `scripts/compute_direct_hit28_20260817.py` | Implemented; frozen under `results/experiments/interim_6_2_offline_20261117/size_matched_hit28/` |
| Human rubric + blinded packets + IRR tooling | `scripts/build_human_eval_packets_28.py`, `scripts/summarize_human_eval_agreement.py` | Packets/blanks ready; ratings await independent humans |
| Bid-price / duration field audit | `scripts/audit_bid_price_duration_fields_20261117.py` | Coverage audit done; numeric validation blocked until fields confirmed |
| Expand toward 352: eligibility inventory | `scripts/inventory_full_352_eligibility_20261117.py` | Inputs/runner present; tender runs not executed |
| Award → construction handoff mapping | `src/stages/execution_handoff.py` | Mapping payload ready; construction sim not auto-started |

## Ablations A1–A4 (code ready; runs gated)

CLI: `python main.py --case-id CASE-0001 --ablation A1` (likewise A2/A3/A4).

| ID | Mechanism removed | Implementation |
|---|---|---|
| A1 | Multi-member firm discussion | `AblationConfig.single_agent_firm` → only final agent speaks |
| A2 | Negotiation-based consortia | Rule pairs lead with first willing partner; skips discussion/negotiation |
| A3 | Reconsideration after failure | Reconsideration stage no-ops and logs skip |
| A4 | Cross-stage memory | `company_package_memory` / `owner_package_memory` return empty |

Protocol for an authorized run:

1. Fix candidate pool, model, temperature, and case list to the interim compact 28 (or declared subset).
2. Run arms: `none`, `A1`, `A2`, `A3`, `A4`.
3. Each arm × 3–5 seeds; write under `runs/<experiment_id>/<arm>/seed-<k>/`.
4. Score with `scripts/aggregate_tender_multirun_metrics.py --run-root ...` and always include size-matched baselines.
5. Freeze accepted outputs into `results/experiments/<experiment_id>/`.

## Repeated runs + sensitivity

- Seeds: declare integer seeds in the run manifest; do not cherry-pick after seeing hit rates.
- Report package hit@1 mean ± SD and size-matched baseline mean ± SD overall and by role.
- Sensitivity levers (one change at a time): candidate pool size, deliberation profile (`full` vs reduced), temperature.
- Aggregate offline with `scripts/aggregate_tender_multirun_metrics.py`.

## Multi-provider comparison

- Client already supports `LLM_PROVIDER` / OpenAI-compatible endpoints (`src/llm_client.py`).
- Protocol: same 28 cases, same ablation=`none`, temperature 0.2, two providers, ≥3 seeds each.
- Compare operational completion and size-matched hit margins; do not merge providers into one hit rate.

## Construction-stage connection

- Tender awards now emit `macro_bridge` mappings in `project_execution_log.json`.
- Next authorized step: compile mapped awards into native/GBA inputs with explicit synthetic assumptions; do not treat mapping-only payloads as executed construction evidence.
