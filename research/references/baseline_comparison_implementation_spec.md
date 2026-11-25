# Implementation spec: stage-isolated external comparisons

**Experiment id:** `baseline_slice_comparisons_20261125`  
**PIC runbook:** [`results/experiments/baseline_slice_comparisons_20261125/README.md`](../../results/experiments/baseline_slice_comparisons_20261125/README.md)  
**Paper prose:** [`research/paper/external_comparison_experiments.md`](../paper/external_comparison_experiments.md)  
**Paper↔code map:** [`research/references/paper_repo_component_map.md`](paper_repo_component_map.md)

This note is for implementers. Historical CP07 and micro-org authorization files are not launch credentials. Frozen Experiment 1 responses are not regenerated.

## 1. Fairness rule

Reuse the frozen OrgBid `multi` artifacts up to the swapped act. Replace only the named engine. Write outputs back as OrgBid dataclasses so judging does not change. Hidden historical partners, contract values, and durations (`data/test_sources/casebank_enterprise_matched/hidden_benchmark_project_enterprises.csv`) are withheld from every engine; `src.baselines.contracts.assert_no_hidden_labels` must run on engine inputs.

```
frozen prefix (project, firms, members, owner packages, …)
        │
        ▼
   one swapped act  →  OrgBid type  →  optional OrgBid suffix (e.g. reconsideration)
        │
        ▼
   slice metrics + tokens + integrity
```

Do **not** edit `src/stages/*.py` in place. Dispatch from `scripts/run_baseline_slice_comparisons_20261125.py` (and later, if needed, a flag in `src/workflow.py`). Third-party trees stay in `vendor/baselines/<name>/`, same contribution boundary as `vendor/gba/`.

## 2. Frozen sample (Experiment 1, 12 projects)

Reference arm is always `multi`. Candidate firms: owner plus two per bidding role.

| Source archive (LFS `full_run.zip`) | Cases |
|---|---|
| `results/experiments/micro-org-1118/` | CASE-0014, 0001, 0002, 0004, 0008, 0050 |
| `results/experiments/micro-org-replication-20261119/` | CASE-0253, 0271, 0319 |
| `results/experiments/micro-org-extension12-20261119/` | CASE-0145, 0089, 0202 |

After `unpack`, each case must expose:

```
runs/baseline-checkpoints/<source>/<CASE>/multi/stage_owner.json
runs/baseline-checkpoints/<source>/<CASE>/multi/stage_bidders.json
runs/baseline-checkpoints/<source>/<CASE>/multi/stage_award.json
runs/baseline-checkpoints/<source>/<CASE>/shared_rosters.json
```

If the layout inside a zip differs, fix `checkpoint_path()` once and record the mapping in `runs/…/unpack_layout.json`. Do not invent missing stages.

Stage files are `{case_id, arm, stage, state: <SimulationState dump>, usage, …}`. Load with `load_simulation_state(payload["state"])`.

**Units already scored in Experiment 1 (multi):** 96 participation decisions, 76 submitted bids, 43 evaluation-and-award products. Paper Table 6’s 90 bid-document *tasks* includes attempts that did not submit; this comparison scores submitted documents unless a later protocol says otherwise.

## 3. What is never swapped

- Case loaders (`src/case_sources.py`, `data/`)
- Hidden labels \(H\)
- Roster generation (shared `shared_rosters.json`)
- Owner packaging (`stage_owner.json`)
- Opening admissibility (who remains on the opened list)
- Licensed revision set after a failed joint bid (`src/stages/reconsideration.py`) except as the **suffix** of Experiment 5
- Project-environment execution (`execution_placeholder` / GBA)
- Rubric files (`config/micro_org_rubric.json`) and the judge protocol in `scripts/micro_org_judge.py`
- Audit logger (`src/run_audit.py`)

## 4. Master swap matrix

| Slice | Frozen start | OrgBid symbol replaced | External method | Adapter | Writes back |
|---|---|---|---|---|---|
| Award | `stage_award.json` after opening | `evaluate_bids` + `make_award_decisions` discussion (2+2 rounds) | TOPSIS; weighted sum sensitivity | `src/baselines/award_topsis.py` (**implemented**) | `EvaluationReport`, `AwardResult` |
| Consortium floor | `stage_bidders.json` after intra-firm rounds 1–3 | `run_inter_company_discussion` + lead `ask_json` CONSORTIUM emit | Language-model multi-issue negotiation; classical automated negotiation | `consortium_llm_delib.py`, `consortium_negmas.py` (stubs) | `Consortium` |
| Intra-firm bid/no-bid | owner packages + shared rosters; **re-run participation only** | body of `AgentRuntime.discuss_async` | Hub-and-spoke / chain / fully connected discussion | `intra_marble.py` (stub) | member `DiscussionMessage`s; `final_agent` still writes `ParticipationDecision` |
| Bid document | participation + consortium + reconsideration from frozen `stage_bidders.json` | three drafting rounds in `generate_bid_documents` | Extract–plan–write–compliance proposal writer | `bidgen_writer.py` (stub) | `BidDocument` (must pass `require_bid_document_shape`) |

## 5. Adapter contracts

### 5.1 Award (done)

```python
rank_package(state, package_id, weight_mode="equal"|"entropy") -> list[RankedBid]
compare_state(state, weight_mode=...) -> list[dict]  # winner agreement, Kendall τ
```

Criteria (opened record + public profile only):

| Attribute | Direction | Source |
|---|---|---|
| Quotation | cost | `BidDocument.quotation` |
| Programme length | cost | first duration in `schedule_commitment` |
| Declared risk | cost | unresolved conditions + public `risk_signals` |
| Public capability | benefit | counts of qualifications, strengths, past projects |

Missing programme values are median-imputed inside the package. Empty opened sets yield no award. Historical names are attached **after** ranking by `src/baselines/historical_winners.py`. A package is historically comparable only when exactly one hidden-benchmark firm matches the package role.

Optional pip extra `baselines-award` (`pymcdm`) may replace the numpy TOPSIS later; do not change the input matrix.

### 5.2 Consortium floor (to implement)

Keep: candidate pool, intra-firm rounds 1–3, reconsideration suffix.

Replace: `src/group_discussion.py:run_inter_company_discussion` and the lead `CONSORTIUM` JSON in `src/stages/consortiums.py`.

Issues (four, shared by both engines): lead identity, work-share bins, price split, risk allocation.

Private reservations: from `Company` profile + package budget. **Not** from \(H\).

Output must pass `require_consortium_shape`. `formed` requires ≥2 distinct members including the lead, all from the authorized candidate set. Invalid or below-reservation deals → `not_formed`, then OrgBid reconsideration.

Language-model floor: clone `https://github.com/S-Abdelnabi/LLM-Deliberation` to `vendor/baselines/llm-deliberation` at a pinned SHA. Each firm is one speaker (the designated representative). Do not use their UN scenario texts.

Classical floor: `pip install '.[baselines-negotiate]'`. `SAOMechanism` + linear additive utilities over the same four issues. Zero model calls.

Set `IMPLEMENTED = True` in the adapter only when a dry-run on CASE-0014 writes a valid `Consortium`.

### 5.3 Intra-firm communication (to implement)

Keep: participation task loop, `require_management_decision`, `final_agent` as the only writer of `ParticipationDecision`.

Replace: the body of `discuss_async` for `bid_participation_decision` when the engine is `marble_*`.

Clone `https://github.com/ulab-uiuc/MARBLE` to `vendor/baselines/MARBLE`. Map:

- `marble_star` → hub-and-spoke (members speak to the decision-holding member)
- `marble_chain` → serial revision (closest to OrgBid `solo` / S4)
- `marble_graph` → fully connected

Call budget: 12 generation calls per firm–package, matching Experiment 1 `multi` order of magnitude. Do not run MARBLE’s research/coding/bargaining games.

Members must not see another firm’s discussion or \(H\). Record leakage in `recovery_events`.

### 5.4 Bid-document writer (to implement)

Keep: who may submit (no_bid and unformed joint bids still do not submit); `require_bid_document_shape`.

Replace: the three LLM drafting rounds in `src/stages/bid_documents.py`.

Clone `https://github.com/tiettuo/claude-bid-gen` to `vendor/baselines/claude-bid-gen`. Map extract/plan/write/compliance onto `BidDocument` fields (`technical_proposal`, `implementation_plan`, `quotation`, `quotation_breakdown`, `schedule_commitment`, `risk_response`, `compliance_statement`, `submission_summary`). Unparseable fields stay empty and fail the shape validator — no silent fill.

## 6. Runner

`scripts/run_baseline_slice_comparisons_20261125.py`

| Command | Network | Spends PIC key? |
|---|---|---|
| `prepare` | no | no |
| `unpack` | LFS only | no |
| `dry-run` | no | no |
| `status` | no | no |
| `run` | award: no; others: yes once implemented | only with dual gate |
| `score` | no (reads hidden CSV post-hoc) | no |

Dual gate for `run`: `--i-authorize-live-calls` **and** `BASELINE_SLICE_ALLOW_LIVE=1`.

Exact PIC commands, token table, and zip/unzip steps: the [PIC README](../../results/experiments/baseline_slice_comparisons_20261125/README.md). Do not duplicate a second set of flags here.

## 7. Judging

Reuse `scripts/micro_org_judge.py` and `config/micro_org_rubric.json` on **new** products only:

- Experiment 6: participation units, R1–R6, paired against frozen `multi`
- Experiment 7: bid-document units, R2/R3/R5 plus mechanical compliance (required sections, invented standards, programme inconsistencies)

Do not re-score frozen Experiment 1 `multi` outputs. Do not merge with CP07 D1–D4 or org-metrics 0–100.

Process criteria P1–P4 apply when the engine leaves a discussion trace.

## 8. Integrity checks (every slice)

Record pass/fail per job:

1. Hidden CSV fields absent from prompts and engine payloads.
2. No other firm’s `agent_discussion_history` in this firm’s context.
3. Exactly one external `ParticipationDecision` / `Consortium` emit / `BidDocument` / `AwardResult` per firm (or owner) per package.
4. Opening disqualified bids never ranked.
5. Token ledger via `LLMCallAuditLogger` (`llm_calls.jsonl`).

A failed integrity check is a method failure, not a footnote.

## 9. Large files (100 MB+) and Git LFS

Already in `.gitattributes`:

```
results/experiments/*/full_run.zip filter=lfs diff=lfs merge=lfs -text
```

GitHub hard-rejects blobs ≥ 100 MB that are not LFS. Unpacked stage JSON, `llm_calls.jsonl`, model caches, and vendor trees routinely exceed that.

**PIC after a run**

1. Leave summaries (`summaries/*.json`, short REPORT) unpacked in `results/experiments/baseline_slice_comparisons_20261125/`.
2. Zip the gitignored run:

```bash
python3 -m scripts.freeze_experiment \
  --run runs/baseline_slice_comparisons_20261125 \
  --id baseline_slice_comparisons_20261125_accepted \
  --keep summaries/REPORT.md,summaries/award_score.json
```

or `zip -r results/experiments/baseline_slice_comparisons_20261125/full_run.zip` from `runs/baseline_slice_comparisons_20261125`.

3. `git add` the zip (LFS pointer) plus summaries. Confirm `git lfs ls-files` lists the zip.
4. Never `git add` an unpacked `llm_calls.jsonl` or checkpoint tree.

**Reviewers unzip to `runs/`, not to `results/`:**

```bash
python3 scripts/run_baseline_slice_comparisons_20261125.py unpack   # Experiment 1 sources
unzip results/experiments/baseline_slice_comparisons_20261125/full_run.zip \
  -d runs/baseline_slice_comparisons_20261125
```

Vendor clones stay in `vendor/baselines/` (gitignored except `README.md`). Pin SHAs in the zip.

## 10. Implementation order

1. Unpack + award TOPSIS on 12 projects (this commit; 0 tokens). Write `summaries/award_score.json`.
2. Count `bid_with_consortium` after dry-run; replace the ~20-floor assumption in `cost_estimate.json` with a **new** dated estimate file if the count differs. Do not rewrite the frozen estimate silently — append `cost_estimate_recount.json`.
3. Implement consortium adapters; PIC smoke CASE-0014 `--max-calls 20`.
4. Implement MARBLE star only; smoke CASE-0014 `--max-calls 8`; then chain and graph.
5. Implement bidgen; smoke CASE-0014 `--max-calls 6`.
6. Judge new products; freeze `full_run.zip`; update `results/README.md`.

Do not start step 3–6 without a new PIC authorization that names the slice, the engine, and `--max-calls`.

## 11. Tests

`tests/test_baseline_slice_comparisons_20261125.py` covers TOPSIS ordering, empty opened set, Kendall τ, hidden-label refusal, live-gate refusal, and idempotent `prepare`. Add adapter tests next to each new engine; they must use scripted LLM stubs, not the PIC key.
