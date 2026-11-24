# External dialogue PIC package

**Audience:** model / experiment PIC who will authorize and run paid calls.  
**Experiment id:** `external_dialogue_generation_20261125`  
**Status:** prepared for launch; **does not auto-start**. Offline baseline scores under `results/experiments/external_baseline_comparison_20261123/` stay frozen. Historical authorization files are **not** a credential for this run.

## Why this exists

The offline external comparison ranked awards (pymcdm), checklist-scored frozen bids, and scored one frozen consortium agreement — all with **0 model calls**. It did **not** generate:

1. the **LLM-Deliberation** negotiation dialogue for that consortium game  
2. a paired **Capstone** consortium deliberation + decision on the same firms/issues  
3. an owner **award decision dialogue** on a frozen package (counterpart to silent TOPSIS)

This package generates those three dialogue arms with one PIC command.

## What is frozen here

| Path | Role |
|---|---|
| `game/case-0150_contractor_package/` | LLM-Deliberation-compatible game (same as offline baseline) |
| `award_packet/case-0002_contractor_package/packet.json` | Frozen bids, evaluation excerpt, owner roster, TOPSIS row |
| `../scripts/run_external_dialogue_generation_20261125.py` | Canonical CLI |
| `../scripts/external_dialogue_generation.sh` | Thin one-command wrapper |

## One command

From **repo root** (recommended):

```bash
# Offline prepare + dry-run only
bash scripts/external_dialogue_generation.sh all

# LIVE (dual gate)
EXTERNAL_DIALOGUE_ALLOW_LIVE=1 bash scripts/external_dialogue_generation.sh all \
  --i-authorize-live-calls
```

Equivalent stepwise:

```bash
python3 scripts/run_external_dialogue_generation_20261125.py prepare
python3 scripts/run_external_dialogue_generation_20261125.py dry-run
python3 scripts/run_external_dialogue_generation_20261125.py status

EXTERNAL_DIALOGUE_ALLOW_LIVE=1 python3 scripts/run_external_dialogue_generation_20261125.py run \
  --i-authorize-live-calls
```

### Live-run gates

1. Pass `--i-authorize-live-calls`.
2. Set `EXTERNAL_DIALOGUE_ALLOW_LIVE=1`.
3. Provider credentials must already be available to `OpenAICompatibleClient.from_env` (same stack as other live Capstone runs; default model `deepseek-flash`).
4. Outputs go under **`runs/external_dialogue_generation_20261125/live/`** (gitignored). Resume is safe: existing `response.json` files are skipped.

## Arms and planned calls

Exact counts are written into `results/experiments/external_dialogue_generation_20261125/protocol.json` by `prepare`. Default plan:

| Arm | What it generates | Approx. calls |
|---|---|---:|
| `llm_deliberation` | External cooperative negotiation rounds + p1 final deal on case-0150 game | 13 (12 rounds + final) |
| `capstone_consortium_decision` | Capstone-style firm negotiation + lead role-split decision on the **same** game | 7 |
| `capstone_award_decision` | Owner-side discussion + final award on case-0002 contractor package | 7 |
| **Total** | | **~27** |

After the run, each arm writes `runs/.../live/<arm>/summary.json` with the deal/award and, for negotiation arms, utilities under the pre-written secret scores.

## Time & cost

From `prepare` → `cost_estimate.json` (assumes ~3.5k tokens / call, ~8 s / call):

- ~27 calls → ~95k tokens  
- serial wall clock ideal ~4 minutes; with overhead / rate limits budget **15–30 minutes**  
- Quote money from the current provider dashboard (repo does not pin a unit price)

## Zip / unzip (outputs too large for GitHub)

Raw request/response JSON under `runs/` is gitignored and should **not** be committed. After a successful live run:

### Pack (PIC → authors)

```bash
python3 scripts/run_external_dialogue_generation_20261125.py pack
# writes: 21 nov updates/external_dialogue_generation_20261125_<UTC>.zip
```

What is inside the zip:

- `external_dialogue_generation_20261125/live/**` — all request/response/summary files  
- `external_dialogue_generation_20261125/experiment_meta/{protocol,cost_estimate,sample_manifest,index}.json`

Keep only the zip (or a cloud link) for bulk transfer. Do **not** add the unzipped live tree to git.

### Reclaim (authors machine / later agent)

```bash
python3 scripts/run_external_dialogue_generation_20261125.py reclaim \
  --zip '21 nov updates/external_dialogue_generation_20261125_<UTC>.zip'
```

This restores files under:

- `runs/external_dialogue_generation_20261125/live/`  
- small meta copies under `results/experiments/external_dialogue_generation_20261125/`

Optional later freeze of accepted summaries only:

```bash
python -m scripts.freeze_experiment \
  --run runs/external_dialogue_generation_20261125 \
  --id external_dialogue_generation_20261125_accepted \
  --keep live/REPORT.json,live/llm_deliberation/summary.json,live/capstone_consortium_decision/summary.json,live/capstone_award_decision/summary.json
```

(`full_run.zip` then holds the bulk evidence via LFS-friendly archive; keep unpacked summaries small.)

## Claim hygiene

- Report the three arms separately; do not merge into one “baseline score.”  
- LLM-Deliberation success uses the **pre-written** secret scores from company-file stems (same rule as the offline baseline).  
- Capstone award dialogue is compared to silent TOPSIS / historical award as overlap flags only.  
- Do not overwrite `external_baseline_comparison_20261123` offline metrics.

## Not in scope

- Regenerating pymcdm rankings  
- Running bid-gen document production (still needs its own interactive planning step)  
- Macro lifecycle / e2e re-sims  
- Expanding beyond the locked protocol without a new experiment id
