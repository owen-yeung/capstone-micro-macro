#!/usr/bin/env bash
# One-command PIC wrapper for external dialogue generation.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CMD="${1:-}"
if [[ -z "$CMD" ]]; then
  echo "Usage: $0 {prepare|dry-run|status|run|pack|reclaim|all} [extra args...]"
  echo "Live one-shot:"
  echo "  EXTERNAL_DIALOGUE_ALLOW_LIVE=1 $0 all --i-authorize-live-calls"
  exit 2
fi
shift || true
PY=(python3 scripts/run_external_dialogue_generation_20261125.py)

case "$CMD" in
  prepare|dry-run|status|run|pack|reclaim)
    exec "${PY[@]}" "$CMD" "$@"
    ;;
  all)
    "${PY[@]}" prepare "$@"
    "${PY[@]}" dry-run
    # Live only when both gates are present in the remaining args / env.
    if [[ "${EXTERNAL_DIALOGUE_ALLOW_LIVE:-}" == "1" ]]; then
      exec "${PY[@]}" run "$@"
    else
      echo "Prepared + dry-run complete. To run live:"
      echo "  EXTERNAL_DIALOGUE_ALLOW_LIVE=1 bash scripts/external_dialogue_generation.sh run --i-authorize-live-calls"
      exit 0
    fi
    ;;
  *)
    echo "Unknown command: $CMD" >&2
    exit 2
    ;;
esac
