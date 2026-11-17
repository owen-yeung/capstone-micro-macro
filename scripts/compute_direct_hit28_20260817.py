#!/usr/bin/env python3
"""Recompute package hit@1 and size-matched baseline for the frozen 28-case archive.

Offline only: reads archived awards and the hidden benchmark CSV. Does not call models.
Restores the reporting entrypoint referenced by
validation/benchmark_ge3_compact/results/final_28_20260817/README.md.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.tender_metrics.size_matched_baseline import (  # noqa: E402
    aggregate_package_scores,
    score_archived_28_cases,
)

DEFAULT_CASES = ROOT / "validation/benchmark_ge3_compact/results/final_28_20260817/cases"
DEFAULT_BENCH = ROOT / "validation/benchmark_ge3_compact/data/hidden_benchmark_project_enterprises.csv"
DEFAULT_OUT = ROOT / "results/experiments/interim_6_2_offline_20261117/size_matched_hit28"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases-root", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--benchmark-csv", type=Path, default=DEFAULT_BENCH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packages = score_archived_28_cases(args.cases_root, args.benchmark_csv)
    summary = aggregate_package_scores(packages)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    packages_path = args.output_dir / "package_scores.json"
    summary_path = args.output_dir / "summary.json"
    report_path = args.output_dir / "REPORT.md"
    packages_path.write_text(json.dumps(packages, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_render_report(summary), encoding="utf-8")
    overall = summary["overall"]
    print(
        f"packages={overall['hits']}/{overall['denominator']} "
        f"hit_rate={overall['hit_rate']:.3f} "
        f"size_matched={overall['mean_size_matched_baseline']:.3f} "
        f"naive={overall['mean_naive_single_draw_baseline']:.3f}"
    )
    print(f"wrote {summary_path}")
    return 0


def _render_report(summary: dict) -> str:
    overall = summary["overall"]
    lines = [
        "# Size-matched hit@1 (frozen 28-case archive)",
        "",
        "Offline recomputation of interim §5.4 / Formula (6). No model calls.",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Package hits | {overall['hits']}/{overall['denominator']} |",
        f"| Hit rate | {overall['hit_rate']*100:.1f}% |",
        f"| Size-matched baseline | {overall['mean_size_matched_baseline']*100:.1f}% |",
        f"| Naive single-draw baseline | {overall['mean_naive_single_draw_baseline']*100:.1f}% |",
        f"| Margin vs size-matched | {overall['margin_vs_size_matched']*100:.1f} points |",
        "",
        "## By role",
        "",
        "| Role | Hits | Hit rate | Size-matched baseline | Margin |",
        "|---|---:|---:|---:|---:|",
    ]
    for role, bucket in summary["by_role"].items():
        lines.append(
            f"| {role} | {bucket['hits']}/{bucket['denominator']} | "
            f"{bucket['hit_rate']*100:.1f}% | {bucket['mean_size_matched_baseline']*100:.1f}% | "
            f"{bucket['margin_vs_size_matched']*100:.1f} |"
        )
    case_any = summary["case_any_hit"]
    lines.extend(
        [
            "",
            f"Case-level any-hit: {case_any['hits']}/{case_any['denominator']} "
            f"({case_any['rate']*100:.1f}%).",
            "",
            summary["reporting_rule"],
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
