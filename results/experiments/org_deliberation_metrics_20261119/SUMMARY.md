# Organization deliberation metrics (2026-11-19)

Offline re-analysis of frozen CP07 grades/process traces and the macro first fixed block. **No new external data. No overwrite of frozen business_review scores. new_model_calls=0.**

Generated at (UTC): 2026-11-19T09:23:23.442906+00:00

## Scope

- CP07 graded windows loaded: 286
- Complete D3–S4 paired windows: 94
- LLM-judged subset: 12 windows (3/role, fixed hash `org-metrics-20261119`)

## A. Outcome quality (frozen D1–D4)

Primary contrast is **D3 − S4** (call-count matched). Values are project-equal means of window deltas.

| Metric | Project-mean Δ (D3−S4) | Exploratory 95% PI | LOO range | Window n_pos/neg/zero |
|---|---:|---|---|---|
| D1 | -0.1042 | [-0.1458, -0.0625] | [-0.1064, -0.0957] | 0/10/84 |
| D2 | 0.0306 | [-0.0007, 0.0622] | [0.0227, 0.0355] | 23/17/54 |
| eval_D3 | 0.0312 | [-0.0312, 0.0938] | [0.0106, 0.0426] | 13/10/71 |
| D4 | -0.1042 | [-0.1458, -0.0625] | [-0.1064, -0.0957] | 0/10/84 |

Arm means (window-equal, complete triples preferred but reported on available rows):

| Arm | D1 | D2 | eval-D3 | D4 |
|---|---:|---:|---:|---:|
| S | 0.766 | 0.846 | 1.691 | 1.766 |
| D3 | 0.872 | 0.863 | 1.830 | 1.872 |
| S4 | 0.979 | 0.832 | 1.798 | 1.979 |

Joint tradeoff (window): D2↑ & D1 not↓ = 0.234; D2↑ & D1↓ = 0.011 (n=94).

### Cost-normalized

| Arm | mean total tokens | D2 / 1k tokens | D1 / 1k tokens |
|---|---:|---:|---:|
| S | 5079 | 0.1760 | 0.1553 |
| D3 | 19261 | 0.0472 | 0.0475 |
| S4 | 19394 | 0.0449 | 0.0536 |

D3−S4 mean token delta: -132.4; D2 delta: 0.0312.

## D. Sensitivity (full vs missing_core)

Signed delta = score(missing_core) − score(full). Larger absolute movement = more sensitive.

| Arm | mean ΔD1 | mean ΔD2 | action flip rate |
|---|---:|---:|---:|
| S | -0.4783 | -0.1080 | 0.978 |
| D3 | -0.2609 | -0.0580 | 1.000 |
| S4 | -0.0435 | -0.0072 | 1.000 |

Abs-sensitivity: D3 more sensitive than S4 on D1 in 10/46 bases (mean |Δ|D3−|Δ|S4 = 0.2174).

Annotated-action disagreement D3 vs S4 (all paired windows): 0.851.

## B/C. Process proxies (lexical, all D3 jobs)

Mean pairwise Jaccard across D3 role comments: 0.274 (n=94).
Mean unique-token fraction: 0.485.
Mean unique→final coverage (dropout importance proxy): 0.222.

## F. LLM-judged subset

Windows scored: 12.

O1 means: {'D3': 5.083333333333333, 'S4': 4.416666666666667}
O2 means: {'D3': 0.9236110833333333, 'S4': 0.9583333333333334}
Rubric means: {"D3": {"R1": 1.75, "R2": 1.6666666666666667, "R3": 0.9166666666666666, "R4": 1.4166666666666667, "R5": 1.6666666666666667}, "S4": {"R1": 2, "R2": 1.5833333333333333, "R3": 2, "R4": 1.8333333333333333, "R5": 2}}
R6 preference counts: {'tie': 3, 'S4': 8, 'D3': 1} (D3 win rate excl. ties: 0.1111111111111111)

Scorer identity: Cursor agent acting as researcher-assisting LLM judge on blinded arm labels where noted in the score file; not an external human expert.

## E. Macro transmission (first fixed block)

On the first fixed macro block, intra-firm deliberation did not change consumable commercial actions or downstream state. Process/text metrics remain the primary differentiation surface until decision variables are consumed differently.

O4 D3−S4: {'comparable_actor_pairs': 2, 'disagreements': 0, 'fraction': 0.0, 'not_independent_project_pairs': True}

## Claim hygiene

- Axes are reported separately; no composite “system better” score.
- D3 shows higher abs-sensitivity to missing_core and higher action divergence vs S4; whether that is desirable depends on whether flips are toward grounded deferral.
- On frozen D1/D4, S4 often matches or exceeds D3; D2/eval-D3 slightly favor D3 in this sample.
- Macro T-path remains null on the first block — do not claim downstream project gains from this block.

## Relation to upstream `micro-org-*` (2026-11-19 merge)

Parallel organization-mechanism line under `results/experiments/micro-org-1118/` (and replication/extension). **Not a drop-in replacement for this CP07 battery** and scores must **not** be pooled:

| | This experiment | `micro-org-*` |
|---|---|---|
| Task surface | Frozen CP07 free-generation business cards | Live tender pipeline stages (策划／决策／投标／定标) |
| Arms | S / D3 / S4 | single / solo / multi (rough analogy only) |
| Primary grades | Frozen D1–D4 (0–2) | Rubric v2 R1–R6 (1–5) |
| Subset labels R1–R6 here | Separate LLM subset rubric on CP07 texts | Different scale/definitions — name collision only |

Rough arm map for narrative only: S≈single, S4≈solo, D3≈multi. Upstream finding that most multi vs single gain is multi-step (solo) rather than multi-role is thematically consistent with S4 strength on D1/D4 here; do not treat either line as confirming the other numerically.

## Artifacts

- `summary.json` — machine-readable aggregate
- `derived/window_pairs.json` — per-window paired metrics
- `scores/subset_llm_scores.json` — LLM judge scores for fixed subset
- `packets/` — texts used for subset judging

