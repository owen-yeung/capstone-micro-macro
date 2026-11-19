# Data lifecycle of the Capstone micro–macro evaluation system

This note describes how evidence moves from real-world project archives to frozen, citable evaluation records. It is written for readers who have not opened the repository. Paths below are relative to the repository root.

## 1. Object of study

The Capstone study asks whether, under a fixed set of business facts and constraints, a model’s **outward business answer**—typically a bid, no-bid, or conditional intention for a construction-related role—is *appropriate* for that task card. Appropriateness is not “did the firm win historically.” Historical award and cost outcomes are deliberately withheld from the answer key.

Four research questions structure the work (`research/PLAN.md`):

| Question | Contrast | Measured products |
|---|---|---|
| RQ1 Judgment quality | Same card; generator versions; full vs missing materials | Action appropriateness (D1), factor coverage (D2), executability / trade-off grades (D3/D4) |
| RQ2 Organization | Single-shot vs multi-step same-role vs multi-role deliberation | Quality gaps, issue handling, strategy, resource cost |
| RQ3 Feedback | No feedback vs settlement-linked feedback | Rule-compliant adaptation; invariant constraints |
| RQ4 Project consequences | Micro decisions under native macro simulation | Pricing, contract, cost, schedule, quality, risk |

Macro simulation engines (`vendor/gba/`, `integration/`) supply an execution environment. They are not claimed as the micro contribution. Metrics are reported separately; there is no single “system score.”

## 2. Upstream archival inputs

Real projects and firms enter as tabular and dossier material under `data/` (large tables may use Git LFS). After deduplication the working universe is approximately **331 project groups**, **904 enterprises**, and **433 labeled project–role units**, drawn from **352** raw project rows (`data/README.md`).

These sources yield:

- company fields that may be shown on a card;
- project facts that bind the scenario;
- explicit **gaps** (`not_supplied`) and **unresolved conditions** that must remain open unless verified.

Matched case banks and validation extracts also live under `validation/` and related Capstone experiment trees. Outcome labels (award, final cost) are **not** used as ground truth for micro scoring.

## 3. Task-card construction (micro cases)

A **task card** is a frozen evaluation instrument: role, variant, facts, allowed company fields, missing fields, conditions, scoring factors, and examples of acceptable vs inappropriate actions. Cards are versioned with hashes so later scoring cannot silently drift.

Important packs include:

| Pack | Role in design | Location (under `Capstone报告/验证体系/`) |
|---|---|---|
| Rubric v2 + early cards | Metric definitions and early scenarios | `指标补充/2026-11-12_业务结果评价规范_v2/` |
| CP00 / CP01 | Original and new-core micro close-outs | `实验/2026-11-12_CP零调用准备/CP00|CP01/` |
| CP08 | Broad micro expansion (≈232 candidates → 464 cards) | `实验/2026-11-13_CP08全量微观扩样/` |
| CP07 | Organization contrast (S / D3 / S4 processes) | `实验/2026-11-13_CP07组织质量对照/` |

Typical roles are **contractor**, **supplier**, **designer**, and **supervisor**. Variants contrast **full** materials with **missing_core** materials. CP08 arms compare generator versions (`v2_4`, `v2_5`); CP07 arms compare organizational processes at a fixed generator version.

## 4. Model generation and response storage

For each card × arm × repeat × attempt, the system issues a model call and stores a job artifact, for example:

- version arms: `…/run/jobs/{window}-{arm}-r{repeat}/attempt-{n}.json`;
- organization finals (CP07): `…/run/jobs/{window}-{arm}-r1/step-4.json`.

Each record retains program status (`accepted`, validation failures, unknown-provider attempts, and so on), request metadata, and content. Budget ledgers and unknown requests are treated as historical facts: they are not rewritten because later results look inconvenient (`AGENTS.md`).

### Public answer versus private scratchpad

Scoring uses only the **outward public business object**—the decision-facing JSON the firm would expose. Private fields such as `thoughts` or internal company assessments are excluded from the scoring view (`content_view` in `scripts/review_capstone_all_20261113.py`). If the outward payload is unreadable or not uniquely recoverable, **no synthetic grade** is invented.

## 5. Mechanical gates (eligibility, not grades)

Before business scoring, forward tooling in `src/generation_validation/` applies **mechanical gates** (`research/generation_validation/README.md`):

1. Is there a readable unique outward answer?
2. Are required public sections present (with a soft path for alternate compact schemas such as `decision` / `content`)?
3. Do soft heuristics flag invented-fact or ungrounded-promise patterns?

Gates emit structured **codes**. Soft hits are hints only. They never assign D1–D4. An answer is `eligible_for_business_scoring` only when readable and free of blocking failures. Denominators in readiness reports keep unread, unscored, and gate-blocked counts visible.

Related forward tools—structured draft/adjudication sheets, discrimination anchors, blinding and order-swap helpers, coverage matrices, and expert-slice samplers—support process quality. They do not replace the frozen rubric and do not overwrite historical grades.

## 6. Adjudication with exact quotes

Eligible answers are scored against the card’s factors and action rules. Each judgment must carry **exact substrings** of the outward text as evidence, plus a short reason. Where the protocol requires detailed scoring, ordinal D3/D4 scores are included.

Two adjudicator identities appear in the archive and must not be conflated:

| Identity | Meaning |
|---|---|
| Author-assisted AI | Participated in designing the original pipeline; exploratory; not blind; not an external human expert |
| Independent second LLM provider (GV20261117) | Separate provider (Cursor); original pipeline was not developed with Cursor; not an external human expert; not blind |

The GV20261117 waves cleared the remaining gate-eligible CP08/CP07 backlog (+1,036 citation-backed reviews). Identity metadata for those reviews was corrected in `results/experiments/generation_validation_enhancement_20261117/reviewer_identity_correction_20261118.json`. Pre-Cursor author-assisted records keep their original identity. Audience overview: `results/experiments/generation_validation_enhancement_20261117/THREAD_SUMMARY.md`.

## 7. Ingest, recheck, and immutability

Authored compact labels (under `…/2026-11-13_总实验收尾/manual_labels/`) are expanded and ingested by `scripts/save_capstone_authored_compact_20261113.py` / `scripts/review_capstone_all_20261113.py`:

1. Reload response and task card; verify quote offsets.
2. Write `business_review/{cohort}/{window}-{arm}-r{repeat}-a{attempt}.json` with hashes of response and card, factor evidence, and reviewer identity.
3. Persist a same-author evidence **recheck** under `business_recheck/` that verifies quotes still match; typical conclusion is `no_change`.

Storage obeys a create-or-exact-replay rule: prepared artifacts that would change bytes are refused. Corrections of substance are appended under new paths (for example revision trees); **initial grades are not replaced**. Unknown provider attempts are not silently replayed.

## 8. Aggregation, readiness, and long-term freezing

Cohort **readiness** JSON files under `…/2026-11-13_总实验收尾/` report planned slots, returned answers, readable answers, pending scores, rechecks, and gate blocks. Paper-facing tables and summaries are derived from these sealed trees.

Long-lived experimental packages are frozen under `results/experiments/<id>/` and indexed from `results/README.md`. Temporary workspaces under `runs/` are gitignored: after acceptance, lasting inputs, responses, scores, logs, and summaries must be copied into `results/experiments/` so research evidence does not exist only in an ignored directory (`AGENTS.md`).

Compatibility trees (`Capstone报告/验证体系/`, `output/integration/`, `validation/`) remain as archival evidence; they are not an automatic re-execution queue.

## 9. Macro branch (downstream, separate)

Selected cases can be driven into native macro chains (tender, fulfillment, feedback). Those chains produce transaction and simulation observables (T- and F-metrics). A complete micro task card does **not** automatically imply that the same project is suitable for an existing macro DBB chain. Macro evidence is therefore stratified and reported separately from micro judgment quality.

## 10. Lifecycle diagram (logical)

```text
Archival dossiers (data/)
        │
        ▼
Frozen task cards (facts, gaps, factors, role, variant)
        │
        ▼
Model jobs / attempts (run/jobs/…; outward ≠ thoughts)
        │
        ▼
Mechanical gates ──blocking──► unscored / blocked denominator
        │ eligible
        ▼
Cited adjudication (author-assisted OR second LLM provider)
        │
        ▼
business_review + business_recheck  (immutable once sealed)
        │
        ├─► readiness / cohort summaries
        ├─► results/experiments/ freeze + results/README index
        └─► optional macro simulation branch (RQ4 / feedback)
```

## 11. How to read the archive

1. Start at `research/PLAN.md` for questions and metrics; `research/NEXT_STEPS.md` for open work.
2. Use `results/README.md` as the navigation index for frozen experiment packages.
3. Treat `business_review/` scores as historical facts: cite them, do not overwrite them.
4. Distinguish **generator quality** (D1–D4 on outward answers) from **process tooling** (gates, coverage, expert-slice slots) and from **macro outcomes**.
5. When comparing adjudicator pools, separate author-assisted records from GV20261117 second-provider records.

---

*This document describes the repository’s evidence lifecycle as operated for Capstone micro evaluation. It does not redefine frozen protocols in `research/references/`.*
