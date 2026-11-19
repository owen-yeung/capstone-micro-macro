# Organization deliberation metrics (2026-11-19)

Offline battery comparing **multi-role intra-firm deliberation (D3)** to **same-role four-step review (S4)** and single-shot **S**, using frozen CP07 grades/process traces and the macro first fixed block.

## What this is

- Quantitative re-analysis of existing scores (A, D, cost, action divergence).
- Lexical process proxies for role specialization / leave-one-role importance (B/C).
- Researcher-assisting LLM judge scores on a fixed 12-window hash subset (O1/O2, R1–R6).
- Macro transmission table confirming null T-path on the first fixed block (E).

## What this is not

- No new external corpora or projects.
- No overwrite of `business_review/CP07` grades.
- No new paid model API calls (`new_model_calls: 0`).
- Not an external human expert panel; not proof of real-world project performance.
- Not a live member-dropout / order-shuffle re-run (those remain protocol + offline proxies).

## How to reproduce

```bash
python3 scripts/analyze_org_deliberation_metrics_20261119.py
```

Requires frozen paths under `Capstone报告/验证体系/实验/…` and optional `scores/subset_llm_scores.json`.

## Primary outputs

| File | Role |
|---|---|
| `SUMMARY.md` | Human-readable results + claim hygiene |
| `summary.json` | Machine-readable aggregate |
| `scores/subset_llm_scores.json` | LLM judge scores for 12 windows |
| `derived/window_pairs.json` | Per-window paired metrics |
| `packets/` | Texts used for subset judging |

## Headline pattern (see SUMMARY for numbers)

- **D2 / eval-D3**: small project-equal edge for D3 over S4.
- **D1 / D4**: S4 ahead; D3 more abs-sensitive to `missing_core`.
- **Process**: D3 subset O1 slightly higher; O2 similar; R2 favors D3, R3/R4 favor S4; R6 prefs D3 1 / S4 8 / tie 3 after batch_b/d adjudication.
- **Macro first block**: no D3−S4 commercial or state divergence.

## Relation to upstream `micro-org-*`

Complementary, not substitutive. Upstream `micro-org-1118` / replication / extension score live tender-pipeline arms (`single`/`solo`/`multi`) with rubric v2 (1–5). This battery stays on frozen CP07 S/D3/S4 with D1–D4 plus a separate subset rubric. Do not pool scores or treat label `R1–R6` as shared. See SUMMARY for the arm-map and claim boundary. Protocol/metrics here needed **no regenerate** after the 2026-11-19 upstream merge.
