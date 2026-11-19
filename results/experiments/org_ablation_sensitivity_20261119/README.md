# Organization ablation & input-sensitivity experiment (PIC guide)

**Audience:** model / experiment PIC who will authorize and run paid calls.  
**Experiment id:** `org_ablation_sensitivity_20261119`  
**Status:** prepared for launch; **does not auto-start**. Historical CP07 `authorization.json` is **not** a credential for this run.

## What this is

A **pre-registered, final-only** ablation battery on frozen CP07 prompts:

| Ablation | What changes | Arm | Calls / window |
|---|---|---|---:|
| `dropout_step{1,2,3}` | Remove one D3 role comment from internal proposals, then ask for final | D3 | 3 |
| `order_perm_021` / `order_perm_102` | Reorder the three D3 comments, then final | D3 | 2 |
| `bitflip_gate_D3` / `bitflip_gate_S4` | Mark a pre-registered staffing/unresolved gate as verified, then final | D3 + S4 | 2 |

**Sample:** 8 windows (2 per role), fixed hash seed `org-ablation-20261119` → **56 calls** total.

**Why this design:** tests whether multi-role deliberation is *mechanism-sensitive* (dropout / order / material gate flips) without new external data and without replaying full 4-step processes.

**Not in scope:** macro T1–T8 re-sims; overwriting frozen `business_review` grades; expanding beyond the frozen 56-job ledger without a new protocol version.

## One-command interface

From repo root:

```bash
# 1) Freeze sample + cost estimate (safe, offline)
python3 scripts/run_org_ablation_sensitivity_20261119.py prepare

# 2) Materialize all 56 request JSONs (safe, offline)
python3 scripts/run_org_ablation_sensitivity_20261119.py dry-run

# 3) Check progress
python3 scripts/run_org_ablation_sensitivity_20261119.py status

# 4) LIVE calls (explicit dual gate)
ORG_ABLATION_ALLOW_LIVE=1 python3 scripts/run_org_ablation_sensitivity_20261119.py run \
  --i-authorize-live-calls \
  --max-calls 56 \
  --concurrency 2
```

Convenience wrapper (same commands):

```bash
bash scripts/org_ablation_sensitivity.sh prepare
bash scripts/org_ablation_sensitivity.sh dry-run
ORG_ABLATION_ALLOW_LIVE=1 bash scripts/org_ablation_sensitivity.sh run
```

### Live-run gates (read before spending)

1. You must pass `--i-authorize-live-calls`.
2. You must set `ORG_ABLATION_ALLOW_LIVE=1`.
3. Provider credentials must already be available to `OpenAICompatibleClient.from_env` (same stack as CP07).
4. Outputs go under **`runs/org_ablation_sensitivity_20261119/live/`** (gitignored temp). After acceptance, freeze selected ledgers/summaries into `results/experiments/org_ablation_sensitivity_20261119/`.

Resume is safe: existing `response.json` files are skipped.

## What the PIC is actually running

Each live job:

1. Loads frozen CP07 `request-step-4.json` for the window/arm.
2. Mutates **only** the internal proposal order/membership **or** inserts one `ABLATION_BITFLIP` user message.
3. Issues **one** final completion (`max_completion_tokens=4096`, `temperature=0.2`, model default `deepseek-flash`).
4. Saves `request.json` + `response.json` under `runs/.../live/<job_id>/`.

No intermediate process regenerations. No writes into CP07 job folders. No grade overwrites.

## Time & cost (from past CP07 finals)

Estimates use frozen CP07 **step-4** usage (~317 finals):

| Quantity | Value |
|---|---:|
| Planned calls | **56** |
| Mean tokens / final (hist.) | ~**5,675** total (~4.4k in / ~1.3k out) |
| Estimated tokens (56 × mean) | ~**318k** |
| Median latency / final (hist.) | ~**6.4 s** |
| Ideal wall clock @ concurrency 2 | ~**3–4 min** |
| Likely wall clock with overhead | ~**15–25 min** |
| Pessimistic (rate limits / retries) | ~**30–45 min** |

### Relative scale vs CP07

| | CP07 org quality | This ablation |
|---|---:|---:|
| Planned calls | 864 | 56 (~6.5% of CP07 calls) |
| Rough token sense | D3 job ~19k tokens × many jobs | ~318k tokens ≈ **~17 D3-job equivalents** |

### Money

Repo does not pin a vendor unit price (list prices move). PIC should quote from the **current DeepSeek / provider dashboard** using:

- model: `deepseek-flash` (or the model string in `protocol.json`)
- ~318k total tokens, historically ~77% input / ~23% output on CP07 finals

If your team’s recent CP07 flash spend is known per ~20k tokens, multiply by ~16–17 for a back-of-envelope.

## After the run (analysis)

Offline follow-ups (no extra calls required for first cut):

1. Compare each ablation final vs frozen CP07 final (`annotated_action` / key JSON fields / deferral language).
2. **Dropout:** which dropped role flips the final most often?
3. **Order:** agreement rate across `order_perm_*` vs identity frozen final.
4. **Bit-flip:** directed change rate when the gate is marked verified — D3 vs S4.

Optional second LLM scoring pass can reuse the org-metrics rubric (`R1–R6`) on a hash subset of ablation finals.

## Files

| Path | Role |
|---|---|
| `protocol.json` | Frozen windows, jobs, endpoints, cost estimate |
| `sample_manifest.json` | Window list |
| `cost_estimate.json` | PIC-facing cost block |
| `dry_run_ledger.json` | Offline request materialization ledger |
| `scripts/run_org_ablation_sensitivity_20261119.py` | CLI |
| `scripts/org_ablation_sensitivity.sh` | Thin wrapper |
| `runs/org_ablation_sensitivity_20261119/` | Temp live/dry-run artifacts (gitignored) |

## Claim hygiene

- Report axes separately (robustness vs sensitivity); do not collapse into “D3 win rate.”
- Final-only dropout/order tests **use of existing role text**, not whether roles would have written different comments under dropout.
- Bit-flips are host-injected verifications on frozen cards — not new external evidence corpora.
