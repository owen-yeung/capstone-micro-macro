# Stage-isolated external comparisons (PIC guide)

**Audience:** model / experiment PIC who holds the API key and will authorize paid calls.  
**Experiment id:** `baseline_slice_comparisons_20261125`  
**Status:** protocol frozen. **Award ranking (Experiment 4) can run without an API key** after the Experiment 1 archives are unpacked. Consortium, intra-firm, and bid-document engines are specified, not yet wired; do not set the live gate for those slices until the corresponding adapter’s `IMPLEMENTED` flag is True.  
**Not a credential:** historical CP07 `authorization.json`, old GOAL files, and previous micro-org live flags.

Paper-facing design: [`research/paper/external_comparison_experiments.md`](../../../research/paper/external_comparison_experiments.md)  
Implementer spec: [`research/references/baseline_comparison_implementation_spec.md`](../../../research/references/baseline_comparison_implementation_spec.md)

## What this is

Four comparisons that keep the **project, the firms, and the visible facts** fixed, and replace **one** tendering act at a time. Upstream artifacts come from the frozen organizational (`multi`) arm of Experiment 1 (twelve projects). Hidden historical partners, contract values, and durations stay out of every engine.

| Slice | Experiment | Replaces | Engine(s) | API key? |
|---|---|---|---|---|
| `award` | 4 | Owner ranking and award after opening | `topsis` (primary), `weighted_sum` (sensitivity) | No |
| `consortium` | 5 | Inter-firm negotiation floor only | `llm_delib`, `negmas` | `llm_delib` yes; `negmas` no |
| `intra` | 6 | How members talk on bid/no-bid | `marble_star`, `marble_chain`, `marble_graph` | Yes |
| `biddoc` | 7 | How the bid document is written | `bidgen` | Yes |

One slice and one engine per live invocation. Never mix engines in one graph. Never regenerate owner packaging, opening admissibility, or the licensed revision rule unless the spec for that slice says so.

## 0. Machine setup (once)

From the repository root, with Python 3.12:

```bash
python3 -m pip install -e .
# Optional, only when those engines are actually being implemented:
python3 -m pip install -e ".[baselines-award,baselines-negotiate]"
```

Credentials for paid slices go in **your** `.env` (never commit it). Copy from `.env.example`:

```bash
cp -n .env.example .env
# then set:
# LLM_PROVIDER=deepseek
# DEEPSEEK_API_KEY=...          # PIC key; authors without a key leave this blank
# DEEPSEEK_MODEL=deepseek-flash
# DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
```

Git LFS is required to unpack Experiment 1 archives (the `full_run.zip` files in git are 133-byte pointers until pulled):

```bash
git lfs version
git lfs install
```

## 1. Offline commands (no API key)

```bash
# Freeze protocol + token estimate if missing (safe to repeat)
python3 scripts/run_baseline_slice_comparisons_20261125.py prepare

# Pull LFS archives and unzip into gitignored runs/baseline-checkpoints/
python3 scripts/run_baseline_slice_comparisons_20261125.py unpack

# Materialize job cards from those checkpoints
python3 scripts/run_baseline_slice_comparisons_20261125.py dry-run --slice award --engine topsis

# What is present vs missing
python3 scripts/run_baseline_slice_comparisons_20261125.py status
```

Wrapper (same commands):

```bash
bash scripts/baseline_slice_comparisons.sh prepare
bash scripts/baseline_slice_comparisons.sh unpack
bash scripts/baseline_slice_comparisons.sh dry-run --slice award --engine topsis
bash scripts/baseline_slice_comparisons.sh status
```

If `unpack` says the files are still LFS pointers, `git lfs pull` did not populate the zips. Do not try to `unzip` a 133-byte pointer.

## 2. Award ranking — run this first (no API key, 0 tokens)

Still requires the dual live gate so a mistyped command cannot later spend money. TOPSIS itself issues **no model requests**.

```bash
BASELINE_SLICE_ALLOW_LIVE=1 python3 scripts/run_baseline_slice_comparisons_20261125.py run \
  --i-authorize-live-calls \
  --slice award \
  --engine topsis

BASELINE_SLICE_ALLOW_LIVE=1 python3 scripts/run_baseline_slice_comparisons_20261125.py run \
  --i-authorize-live-calls \
  --slice award \
  --engine weighted_sum

python3 scripts/run_baseline_slice_comparisons_20261125.py score --engine topsis
```

Resume is safe: existing `result.json` files are skipped unless `--force`.

Entropy weights instead of equal weights (still local):

```bash
BASELINE_TOPSIS_WEIGHTS=entropy BASELINE_SLICE_ALLOW_LIVE=1 \
  python3 scripts/run_baseline_slice_comparisons_20261125.py run \
  --i-authorize-live-calls --slice award --engine topsis --force
```

Outputs: `runs/baseline_slice_comparisons_20261125/award/<engine>/<source>/<CASE>/result.json`  
Summary: `results/experiments/baseline_slice_comparisons_20261125/summaries/award_score.json`

## 3. Paid engines — only after the adapter is implemented

The runner will exit with `Engine '…' is specified but not implemented` until the adapter module sets `IMPLEMENTED = True`. When that happens, PIC uses the same dual gate. **Authors without the key send PIC these exact commands.**

Smoke (one project, cap the calls):

```bash
# language-model joint-bid floor, CASE-0014 only
BASELINE_SLICE_ALLOW_LIVE=1 python3 scripts/run_baseline_slice_comparisons_20261125.py run \
  --i-authorize-live-calls \
  --slice consortium \
  --engine llm_delib \
  --case CASE-0014 \
  --max-calls 20

# intra-firm hub-and-spoke on bid/no-bid, CASE-0014 only
BASELINE_SLICE_ALLOW_LIVE=1 python3 scripts/run_baseline_slice_comparisons_20261125.py run \
  --i-authorize-live-calls \
  --slice intra \
  --engine marble_star \
  --case CASE-0014 \
  --max-calls 8

# bid-document writer, CASE-0014 only
BASELINE_SLICE_ALLOW_LIVE=1 python3 scripts/run_baseline_slice_comparisons_20261125.py run \
  --i-authorize-live-calls \
  --slice biddoc \
  --engine bidgen \
  --case CASE-0014 \
  --max-calls 6
```

`--concurrency` will be honoured once those adapters are wired; this commit’s runner does not yet pass it. Keep `--max-calls` on every first paid command.

Full twelve-project runs (only after smoke looks sane):

```bash
BASELINE_SLICE_ALLOW_LIVE=1 python3 scripts/run_baseline_slice_comparisons_20261125.py run \
  --i-authorize-live-calls --slice consortium --engine llm_delib

BASELINE_SLICE_ALLOW_LIVE=1 python3 scripts/run_baseline_slice_comparisons_20261125.py run \
  --i-authorize-live-calls --slice consortium --engine negmas

BASELINE_SLICE_ALLOW_LIVE=1 python3 scripts/run_baseline_slice_comparisons_20261125.py run \
  --i-authorize-live-calls --slice intra --engine marble_star

BASELINE_SLICE_ALLOW_LIVE=1 python3 scripts/run_baseline_slice_comparisons_20261125.py run \
  --i-authorize-live-calls --slice intra --engine marble_chain

BASELINE_SLICE_ALLOW_LIVE=1 python3 scripts/run_baseline_slice_comparisons_20261125.py run \
  --i-authorize-live-calls --slice intra --engine marble_graph

BASELINE_SLICE_ALLOW_LIVE=1 python3 scripts/run_baseline_slice_comparisons_20261125.py run \
  --i-authorize-live-calls --slice biddoc --engine bidgen
```

Judging reused Experiment 1 rubric (`scripts/micro_org_judge.py`) is a **separate** live command, on the new products only. Do not re-judge frozen OrgBid `multi` outputs.

## 4. Token estimate (PIC quote sheet)

Numbers below are **planning estimates** from the frozen Experiment 1 `multi` arm (12 projects: 3,308 generation requests; mean ≈ 6,073 input / 644 output tokens per request). Recalculate from `dry-run` once checkpoints are unpacked. List prices move: quote from the current DeepSeek dashboard.

| Work | Calls | Input tokens | Output tokens | Total tokens | API? |
|---|---:|---:|---:|---:|---|
| Award TOPSIS + weighted sum (12 projects) | 0 | 0 | 0 | **0** | No |
| Consortium language-model floor (assumes ~20 joint-bid attempts × 24 speaker turns) | ~480 | ~2.9M | ~0.31M | **~3.2M** | Yes |
| Consortium classical negotiator | 0 | 0 | 0 | **0** | No |
| Intra-firm, three structures, 96 bid/no-bid tasks, 12 calls each (call-matched to OrgBid `multi`) | 3,456 | ~21.0M | ~2.2M | **~23.2M** | Yes |
| Judge for those 288 new bid/no-bid products (scale from Experiment 1 judge: ~4.1 requests / unit) | ~1,180 | ~5.6M | ~0.65M | **~6.3M** | Yes |
| Bid-document writer, 76 submitted bids × 6 calls | 456 | ~2.8M | ~0.29M | **~3.1M** | Yes |
| Judge for those 76 new documents | ~310 | ~1.5M | ~0.17M | **~1.7M** | Yes |
| **All paid work if every LLM engine is run once** | **~5,900** | **~33.8M** | **~3.6M** | **~37.4M** | Yes |
| Smoke CASE-0014, one intra structure, `--max-calls 8` | ≤8 | ~49k | ~5k | **~54k** | Yes |

Relative scale: Experiment 1 `multi` on 12 projects was 3,308 requests and ~22.2M total tokens. Running **all three** intra-firm structures plus judging is on the order of **one additional Experiment 1 multi arm**, not a small ablation.

Wall clock (order of magnitude, concurrency 2, no rate limits):

| Work | Likely | Pessimistic |
|---|---|---|
| Unpack + award TOPSIS | 10–20 min | 45 min (LFS) |
| Consortium language-model floor | 1–3 h | 6 h |
| Intra-firm three structures | 8–16 h | overnight + retries |
| Bid-document writer | 1–3 h | 6 h |
| Judging | 2–6 h | 12 h |

Money: this repository does not pin a unit price. PIC should price **~37M total tokens, historically ~90% input / 10% output on generation, closer to 90/10 on judging**, model `deepseek-flash` (or the string in `protocol.json`). Experiment 1 reported at most about CNY 83 list-price for *all three OrgBid arms* on 12 projects; that figure **does not** cover these new engines.

After unpack, replace the consortium “~20 floors” assumption with the counted `n_consortium_requests` in `runs/baseline_slice_comparisons_20261125/dry_run_ledger.json`.

## 5. What to zip, what to LFS, what to leave unpacked

`runs/` is gitignored. The only long-lived copy of a finished run is under `results/experiments/`. GitHub rejects files ≥ 100 MB that are not LFS. This repository already LFS-tracks `results/experiments/*/full_run.zip`.

### 5.1 After a slice finishes (PIC)

Keep in git as ordinary files (small):

- `results/experiments/baseline_slice_comparisons_20261125/README.md`
- `protocol.json`, `cost_estimate.json`, `index.json`
- `summaries/*.json` and a short `summaries/REPORT.md` you write from `score`
- `vendor_pins.json` (commit SHAs of any cloned engines)

Zip **everything else** from the gitignored run directory:

```bash
# from repo root
mkdir -p results/experiments/baseline_slice_comparisons_20261125
python3 -m scripts.freeze_experiment \
  --run runs/baseline_slice_comparisons_20261125 \
  --id baseline_slice_comparisons_20261125_accepted \
  --keep summaries/REPORT.md,summaries/award_score.json
```

`freeze_experiment` will not overwrite an existing experiment directory. That is why the archive id is `…_accepted`, not this protocol folder.

If `freeze_experiment` is inconvenient because summaries already live here, zip by hand:

```bash
cd runs/baseline_slice_comparisons_20261125
zip -r ../../results/experiments/baseline_slice_comparisons_20261125/full_run.zip .
# include vendor pins if they only exist under runs/
```

Then:

```bash
git lfs track  # confirm results/experiments/*/full_run.zip is already tracked
git add results/experiments/baseline_slice_comparisons_20261125/full_run.zip
git add results/experiments/baseline_slice_comparisons_20261125/summaries
du -h results/experiments/baseline_slice_comparisons_20261125/full_run.zip
```

If `du` shows ≥ 100 MB, the LFS pointer (133 bytes in git) is the thing that gets pushed; the bytes live in LFS storage. If `git add` of a ≥ 100 MB **unpacked** JSON/jsonl is attempted, GitHub will reject the push — zip it instead.

**Do not commit**

- `.env`, keys, `credentials.json`
- `runs/` (temporary)
- `vendor/baselines/llm-deliberation`, `MARBLE`, `claude-bid-gen` trees
- unpacked checkpoint copies under `runs/baseline-checkpoints/`
- judge caches that duplicate Experiment 1

### 5.2 Where to unzip (reviewers and later PIC)

Experiment 1 sources (needed before award/consortium/intra/biddoc):

```bash
python3 scripts/run_baseline_slice_comparisons_20261125.py unpack
# equivalent manual form:
# git lfs pull --include 'results/experiments/micro-org-1118/full_run.zip,results/experiments/micro-org-replication-20261119/full_run.zip,results/experiments/micro-org-extension12-20261119/full_run.zip'
# unzip results/experiments/micro-org-1118/full_run.zip -d runs/baseline-checkpoints/micro-org-1118
```

This comparison’s own archive:

```bash
git lfs pull --include 'results/experiments/baseline_slice_comparisons_20261125/full_run.zip'
mkdir -p runs/baseline_slice_comparisons_20261125
unzip results/experiments/baseline_slice_comparisons_20261125/full_run.zip \
  -d runs/baseline_slice_comparisons_20261125
```

Accepted freeze:

```bash
git lfs pull --include 'results/experiments/baseline_slice_comparisons_20261125_accepted/full_run.zip'
unzip results/experiments/baseline_slice_comparisons_20261125_accepted/full_run.zip \
  -d runs/baseline_slice_comparisons_20261125_accepted
```

Never unzip into `results/experiments/micro-org-*` (those directories already hold the frozen summaries). Never unzip into `src/`.

## 6. Live-run gates (read before spending)

1. Pass `--i-authorize-live-calls`.
2. Set `BASELINE_SLICE_ALLOW_LIVE=1`.
3. For LLM engines, `OpenAICompatibleClient.from_env` must see `DEEPSEEK_API_KEY` (or `OPENAI_API_KEY`).
4. Outputs go under **`runs/baseline_slice_comparisons_20261125/`** (gitignored). Freeze after acceptance.
5. `--max-calls` on every smoke. Resume skips existing `result.json`.
6. Hidden benchmark CSV is read **only** in `score` / award post-hoc annotation, never by an engine prompt.

## 7. Claim hygiene

- Do not pool the four slices with Experiments 1–3 or with each other.
- Winner agreement with history is not accuracy and is not a claim that OrgBid predicts real awards.
- An organizational layer that matches TOPSIS or a document writer at several times the call count is a negative result unless the quality gap is large enough to justify it.
- Integrity failures (hidden labels in a prompt, another firm’s internal discussion, more than one external voice per firm) count against a method even when the headline outcome looks better.

## Files

| Path | Role |
|---|---|
| `protocol.json` | Frozen jobs, cases, gates |
| `cost_estimate.json` | PIC-facing token block |
| `index.json` | Status stub |
| `summaries/` | Filled after `score` / live runs |
| `scripts/run_baseline_slice_comparisons_20261125.py` | CLI |
| `scripts/baseline_slice_comparisons.sh` | Thin wrapper |
| `src/baselines/` | Adapters (`topsis` live; others stubs) |
| `runs/baseline-checkpoints/` | Unpacked Experiment 1 `multi` stages (gitignored) |
| `runs/baseline_slice_comparisons_20261125/` | Temp live/dry-run artifacts (gitignored) |
