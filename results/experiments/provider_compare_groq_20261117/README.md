# Provider compare: DeepSeek vs Groq/Llama

Cheap second-provider arm for interim §6.2.

## Setup

```bash
# .env (do not commit)
DEEPSEEK_API_KEY=...
GROQ_API_KEY=...
GROQ_MODEL=llama-3.1-8b-instant   # or llama-3.3-70b-versatile
```

## Commands

```bash
# Plan only (default)
python scripts/run_provider_compare_groq_20261117.py

# Smoke with mock client (no paid calls)
python scripts/run_provider_compare_groq_20261117.py --execute --local-test-client --max-cases 1 --seeds 1 --profile smoke

# Authorized paid compare (3 seeds × deepseek + groq)
python scripts/run_provider_compare_groq_20261117.py --execute --seeds 3

# Score completed run dirs later
python scripts/run_provider_compare_groq_20261117.py --score-only
```

Outputs land under this directory as `deepseek__…__seedN/` and `groq__…__seedN/`. Scores are size-matched hit@1 per arm; providers are never merged.
