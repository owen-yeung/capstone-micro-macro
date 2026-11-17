#!/usr/bin/env python3
"""Aggregate package hit@1 mean/SD across repeated tendering run directories.

Use after authorized multi-seed / ablation runs exist. Offline over saved awards.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.tender_metrics.human_eval import mean_sd  # noqa: E402
from src.tender_metrics.size_matched_baseline import (  # noqa: E402
    aggregate_package_scores,
    score_archived_28_cases,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-root",
        type=Path,
        action="append",
        required=True,
        help="Directory containing case-* subfolders with simulated_award_result.json. Repeatable.",
    )
    parser.add_argument(
        "--benchmark-csv",
        type=Path,
        default=ROOT / "validation/benchmark_ge3_compact/data/hidden_benchmark_project_enterprises.csv",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_summaries = []
    hit_rates = []
    baselines = []
    for run_root in args.run_root:
        packages = score_archived_28_cases(run_root, args.benchmark_csv)
        summary = aggregate_package_scores(packages)
        run_summaries.append(
            {
                "run_root": str(run_root),
                "overall": summary["overall"],
                "by_role": summary["by_role"],
            }
        )
        if summary["overall"]["hit_rate"] is not None:
            hit_rates.append(summary["overall"]["hit_rate"])
        if summary["overall"]["mean_size_matched_baseline"] is not None:
            baselines.append(summary["overall"]["mean_size_matched_baseline"])
    payload = {
        "runs": run_summaries,
        "aggregate": {
            "hit_rate": mean_sd(hit_rates),
            "size_matched_baseline": mean_sd(baselines),
            "n_runs": len(run_summaries),
        },
        "note": (
            "Interim §5.5/§6.2 asks for 3–5 repeats with mean and SD. "
            "This script only aggregates existing offline archives."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
