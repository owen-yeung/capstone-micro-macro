# Provider-compare plan (DeepSeek vs Qwen3.5-Flash)

Mode: `execute`.

| Provider | Model | Seed | Output |
|---|---|---:|---|
| qwen | `qwen3.5-flash` | 1 | `/agent/repos/capstone-micro-macro/runs/provider_compare_qwen_20261117/qwen__qwen3.5-flash__seed1` |

Score with size-matched hit@1 after each seed completes.
Do not average DeepSeek and Qwen into one hit rate.
Qwen thinking is disabled (`enable_thinking=false`) for JSON contracts.

Execute:
```bash
python scripts/run_provider_compare_qwen_20261117.py --execute
```

Keys required:
- `DEEPSEEK_API_KEY` for the reference arm
- `DASHSCOPE_API_KEY` (or `QWEN_API_KEY`) for Qwen3.5-Flash
