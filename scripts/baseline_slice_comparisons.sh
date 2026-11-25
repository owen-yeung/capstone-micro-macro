#!/usr/bin/env bash
# Thin wrapper for stage-isolated baseline comparisons (Experiments 4–7).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CMD="${1:-}"
if [[ -z "$CMD" ]]; then
  echo "Usage: $0 {prepare|unpack|dry-run|status|run|score} [extra args...]"
  echo "Award (no API key):"
  echo "  $0 unpack"
  echo "  $0 dry-run --slice award --engine topsis"
  echo "  BASELINE_SLICE_ALLOW_LIVE=1 $0 run --i-authorize-live-calls --slice award --engine topsis"
  echo "  $0 score --engine topsis"
  echo "Paid engines (after adapters are implemented):"
  echo "  BASELINE_SLICE_ALLOW_LIVE=1 $0 run --i-authorize-live-calls --slice intra --engine marble_star --case CASE-0014 --max-calls 8"
  exit 2
fi
shift || true
exec python3 scripts/run_baseline_slice_comparisons_20261125.py "$CMD" "$@"
