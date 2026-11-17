#!/usr/bin/env python3
"""Audit bid-price / duration fields against benchmark coverage (offline).

Interim §6.2: validate reasonableness once benchmark fields are confirmed.
This script only inventories comparability; it does not invent validated matches.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCH = ROOT / "data/test_sources/casebank_enterprise_matched/hidden_benchmark_project_enterprises.csv"
DEFAULT_CASES = ROOT / "validation/benchmark_ge3_compact/results/final_28_20260817/cases"
DEFAULT_OUT = ROOT / "results/experiments/interim_6_2_offline_20261117/price_duration_field_audit"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-csv", type=Path, default=DEFAULT_BENCH)
    parser.add_argument("--cases-root", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def nonempty(value: str | None) -> bool:
    text = (value or "").strip()
    return bool(text) and text not in {"无法获取", "无法获取（仅有开标结果）", "N/A", "n/a", "-"}


def main() -> int:
    args = parse_args()
    with args.benchmark_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    field_stats = {
        "contract_amount": {"nonempty_rows": 0, "projects": set()},
        "contract_duration": {"nonempty_rows": 0, "projects": set()},
        "actual_duration": {"nonempty_rows": 0, "projects": set()},
    }
    samples = defaultdict(list)
    for row in rows:
        case_id = row.get("case_id") or row.get("\ufeffcase_id")
        for field in field_stats:
            if nonempty(row.get(field)):
                field_stats[field]["nonempty_rows"] += 1
                field_stats[field]["projects"].add(case_id)
                if len(samples[field]) < 5:
                    samples[field].append(
                        {
                            "case_id": case_id,
                            "company_id": row.get("company_id"),
                            "value": row.get(field),
                            "role": row.get("company_role_original"),
                        }
                    )

    sim_quotes = []
    parse_failures = Counter()
    for case_dir in sorted(path for path in args.cases_root.iterdir() if path.is_dir()):
        bids = json.loads((case_dir / "bid_documents.json").read_text(encoding="utf-8"))
        for bid in bids:
            quote = bid.get("quotation")
            schedule = bid.get("schedule_commitment")
            parsed_amount = _parse_amount(quote)
            parsed_duration = _parse_duration_months(schedule)
            if quote and parsed_amount is None:
                parse_failures["quotation"] += 1
            if schedule and parsed_duration is None:
                parse_failures["schedule"] += 1
            sim_quotes.append(
                {
                    "case_id": f"CASE-{case_dir.name.split('-', 1)[1]}",
                    "package_id": bid.get("package_id"),
                    "bidder_id": bid.get("bidder_id"),
                    "quotation_raw": quote,
                    "schedule_raw": schedule,
                    "quotation_parsed": parsed_amount,
                    "schedule_months_parsed": parsed_duration,
                }
            )

    summary = {
        "benchmark_rows": len(rows),
        "benchmark_fields": {
            field: {
                "nonempty_rows": stats["nonempty_rows"],
                "distinct_projects": len(stats["projects"]),
                "comparable_now": False,
                "blocker": "Units, currency, contract scope, and package alignment are not yet confirmed.",
                "samples": samples[field],
            }
            for field, stats in field_stats.items()
        },
        "frozen_28_sim_bids": {
            "bid_count": len(sim_quotes),
            "quotation_parsed": sum(1 for row in sim_quotes if row["quotation_parsed"] is not None),
            "schedule_months_parsed": sum(1 for row in sim_quotes if row["schedule_months_parsed"] is not None),
            "parse_failures": dict(parse_failures),
        },
        "validation_status": "blocked_pending_benchmark_field_confirmation",
        "next_required_checks": [
            "Confirm currency and amount unit for contract_amount vs simulated quotation",
            "Confirm whether contract_duration is calendar months and package-scoped",
            "Join only same case + same role/package; do not compare whole-project totals to package bids",
            "Exclude rows marked 无法获取 or otherwise non-numeric",
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "sim_bid_extractions.json").write_text(
        json.dumps(sim_quotes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "REPORT.md").write_text(_report(summary), encoding="utf-8")
    print(f"wrote {args.output_dir / 'summary.json'}")
    return 0


def _parse_amount(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"([0-9]+(?:[.,][0-9]+)*)", str(text).replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _parse_duration_months(text: str | None) -> float | None:
    if not text:
        return None
    raw = str(text)
    month = re.search(r"(\d+(?:\.\d+)?)\s*(个月|月|months?)", raw, flags=re.I)
    if month:
        return float(month.group(1))
    day = re.search(r"(\d+(?:\.\d+)?)\s*(天|日|days?)", raw, flags=re.I)
    if day:
        return float(day.group(1)) / 30.0
    return None


def _report(summary: dict) -> str:
    lines = [
        "# Bid price / duration field audit",
        "",
        f"Benchmark rows: {summary['benchmark_rows']}",
        "",
        "| Field | Non-empty rows | Projects | Comparable now |",
        "|---|---:|---:|---|",
    ]
    for field, info in summary["benchmark_fields"].items():
        lines.append(
            f"| {field} | {info['nonempty_rows']} | {info['distinct_projects']} | {info['comparable_now']} |"
        )
    sim = summary["frozen_28_sim_bids"]
    lines.extend(
        [
            "",
            f"Frozen-28 simulated bids: {sim['bid_count']}; "
            f"quotation parsed {sim['quotation_parsed']}; "
            f"schedule parsed {sim['schedule_months_parsed']}.",
            "",
            f"Status: `{summary['validation_status']}`.",
            "",
            "Required before claiming reasonableness validation:",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in summary["next_required_checks"])
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
