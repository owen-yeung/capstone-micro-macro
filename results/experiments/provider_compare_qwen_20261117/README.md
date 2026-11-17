# Provider-compare: DeepSeek vs Qwen3.5-Flash

Interim §6.2 second-provider arm using Alibaba DashScope OpenAI-compatible API.

| Arm | Provider | Model |
|---|---|---|
| Reference | `deepseek` | `deepseek-chat` (or `DEEPSEEK_MODEL`) |
| Second | `qwen` | `qwen3.5-flash` |

## Commands

```bash
# Dry-run plan only (default)
python scripts/run_provider_compare_qwen_20261117.py

# Local wiring smoke (mock client, no paid calls)
python scripts/run_provider_compare_qwen_20261117.py --execute --local-test-client --max-cases 1 --seeds 1 --profile smoke

# Authorized paid compare (3 seeds × deepseek + qwen)
python scripts/run_provider_compare_qwen_20261117.py --execute --seeds 3

# Score completed seed directories
python scripts/run_provider_compare_qwen_20261117.py --score-only
```

## Keys

- `DEEPSEEK_API_KEY`
- `DASHSCOPE_API_KEY` (or `QWEN_API_KEY`)
- Optional: `QWEN_BASE_URL` (mainland default; use `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` internationally)

Qwen3.5 thinking is disabled in the client (`enable_thinking=false`) so JSON contracts stay stable.

Outputs under `runs/provider_compare_qwen_20261117/` (gitignored). Plans/scores are mirrored here.
