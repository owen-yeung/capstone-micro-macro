#!/usr/bin/env bash
# Thin wrapper for org ablation / input-sensitivity experiment.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CMD="${1:-}"
if [[ -z "$CMD" ]]; then
  echo "Usage: $0 {prepare|dry-run|status|run} [extra args...]"
  echo "Live example:"
  echo "  ORG_ABLATION_ALLOW_LIVE=1 $0 run --i-authorize-live-calls --max-calls 56"
  exit 2
fi
shift || true
exec python3 scripts/run_org_ablation_sensitivity_20261119.py "$CMD" "$@"
