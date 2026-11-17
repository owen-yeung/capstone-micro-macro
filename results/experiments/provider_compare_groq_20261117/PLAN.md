# Provider-compare plan (DeepSeek vs Groq/Llama)

Mode: `dry-run`.

| Provider | Model | Seed | Output |
|---|---|---:|---|
| deepseek | `deepseek-chat` | 1 | `/agent/repos/capstone-micro-macro/runs/provider_compare_groq_20261117/deepseek__deepseek-chat__seed1` |
| deepseek | `deepseek-chat` | 2 | `/agent/repos/capstone-micro-macro/runs/provider_compare_groq_20261117/deepseek__deepseek-chat__seed2` |
| deepseek | `deepseek-chat` | 3 | `/agent/repos/capstone-micro-macro/runs/provider_compare_groq_20261117/deepseek__deepseek-chat__seed3` |
| groq | `llama-3.1-8b-instant` | 1 | `/agent/repos/capstone-micro-macro/runs/provider_compare_groq_20261117/groq__llama-3.1-8b-instant__seed1` |
| groq | `llama-3.1-8b-instant` | 2 | `/agent/repos/capstone-micro-macro/runs/provider_compare_groq_20261117/groq__llama-3.1-8b-instant__seed2` |
| groq | `llama-3.1-8b-instant` | 3 | `/agent/repos/capstone-micro-macro/runs/provider_compare_groq_20261117/groq__llama-3.1-8b-instant__seed3` |

Score with size-matched hit@1 after each seed completes.
Do not average DeepSeek and Groq into one hit rate.

Execute:
```bash
python scripts/run_provider_compare_groq_20261117.py --execute
```
