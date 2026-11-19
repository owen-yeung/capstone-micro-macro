# Generation validation enhancements and GV20261117 adjudication

Audience note: this summarizes the Cursor-thread work that added validation tooling and cleared the gate-eligible CP08/CP07 scoring backlog.

## What this project is scoring

The Capstone work asks models to produce **business-facing bid/no-bid style answers** for construction-related task cards (roles such as contractor, designer, supervisor, supplier). Those answers are then judged against a fixed rubric (action appropriateness D1, factor handling, and sometimes detailed scores D3/D4), with **exact quotes** from the answer as evidence.

Two main cohorts:

- **CP08** — large micro-expansion set
- **CP07** — organization / quality comparison set

## What was enhanced in the validation pipeline

Six tooling pieces were added so scoring is more disciplined and auditable (without auto-assigning grades or calling paid models):

1. **Mechanical gates** — check readability / required structure / invented-fact heuristics before business scoring. Soft path for alternate `decision`/`content` schemas so those answers stay scorable.
2. **Structured score sheets** — separate draft vs adjudication slots; agreement is draft–adjudicator, not inter-rater reliability.
3. **Discrimination anchors** — 24 held-out exemplars across challenge classes × roles, for forward calibration.
4. **Blinding / order-swap helpers** — strip arm/version cues; sealed swap maps (still not true independent blind review).
5. **Coverage matrix** — role × materials × condition × tradeoff cells; empty challenge classes constrain claims.
6. **Expert-slice sampler** — stratified sample for external credibility work.

**Hard rules kept throughout:** no overwriting frozen historical grades; no inventing scores without quotes; no new model API calls for this adjudication work.

## What reviews were produced

After the tooling landed, the remaining **gate-eligible unanswered backlog** was adjudicated in five waves by an **independent second LLM provider** (Cursor). The original scoring pipeline was **not** developed with Cursor, so these reviews are a separate provider—not the original design-participating author-assistant, and not an external human expert.

| Wave | New reviews | Notes |
|------|-------------|--------|
| 1 | 84 | Expert-slice + first CP08 backlog |
| 2 | 120 | Stratified CP08 + CP07 |
| 3 | 152 | Continued backlog |
| 4 | 240 | Some CP08 needed D3/D4 patch via `compact_first_002` |
| 5 | 440 | Cleared the rest of eligible pending |

**Totals after wave 5**

- **+1,036** new citation-backed business reviews (`new_model_calls: 0`)
- Review files: **CP08 ≈926**, **CP07 ≈286**
- Remaining readable + gate-eligible pending: **0 / 0**

Each review is a compact labeled judgment (D1, factors, D3/D4 when required) with **exact outward quotes**, then mechanically ingested into the `business_review` / `business_recheck` trees under the corrected identity labels. See `reviewer_identity_correction_20261118.json`.

## How to read the result

This is a **process + coverage completion** outcome: the validation tooling is in place, and the eligible unscored pile for CP08/CP07 was filled by a **second LLM provider**, distinct from the original pipeline’s author-assisted reviews. It does **not** claim external human-expert reliability or a new success-rate headline for the model.

## Related paths

- Protocol: `research/generation_validation/README.md`
- Progress: `adjudication_progress_20261117.json` and `..._wave2.json` … `..._wave5.json`
- Labels: `Capstone报告/验证体系/实验/2026-11-13_总实验收尾/manual_labels/GV20261117_*`
