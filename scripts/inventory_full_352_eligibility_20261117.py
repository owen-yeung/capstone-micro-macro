#!/usr/bin/env python3
"""Inventory 352-case tendering expansion readiness (offline, no model calls)."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECTS = ROOT / "data/test_sources/casebank_enterprise_matched/simulation_input_projects.csv"
DEFAULT_BENCH = ROOT / "data/test_sources/casebank_enterprise_matched/hidden_benchmark_project_enterprises.csv"
DEFAULT_FULL = ROOT / "validation/full_352_cases"
DEFAULT_COMPACT = ROOT / "validation/benchmark_ge3_compact"
DEFAULT_OUT = ROOT / "results/experiments/interim_6_2_offline_20261117/full_352_eligibility"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects-csv", type=Path, default=DEFAULT_PROJECTS)
    parser.add_argument("--benchmark-csv", type=Path, default=DEFAULT_BENCH)
    parser.add_argument("--full-bundle", type=Path, default=DEFAULT_FULL)
    parser.add_argument("--compact-bundle", type=Path, default=DEFAULT_COMPACT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with args.projects_csv.open(encoding="utf-8-sig", newline="") as handle:
        projects = list(csv.DictReader(handle))
    with args.benchmark_csv.open(encoding="utf-8-sig", newline="") as handle:
        bench = list(csv.DictReader(handle))
    project_ids = [(row.get("case_id") or row.get("\ufeffcase_id")) for row in projects]
    bench_by_case = defaultdict(list)
    for row in bench:
        case_id = row.get("case_id") or row.get("\ufeffcase_id")
        bench_by_case[case_id].append(row)

    frozen_28 = set()
    selected = args.compact_bundle / "selected_case_ids.txt"
    if selected.exists():
        frozen_28 = {line.strip() for line in selected.read_text(encoding="utf-8").splitlines() if line.strip()}
    else:
        cases_dir = args.compact_bundle / "results/final_28_20260817/cases"
        if cases_dir.exists():
            frozen_28 = {f"CASE-{path.name.split('-', 1)[1]}" for path in cases_dir.iterdir() if path.is_dir()}

    full_summary = {}
    summary_path = args.full_bundle / "bundle_summary.json"
    if summary_path.exists():
        full_summary = json.loads(summary_path.read_text(encoding="utf-8"))

    role_coverage = Counter()
    cases_with_any_ref = 0
    for case_id in project_ids:
        roles = {(row.get("company_role_original") or "").strip() for row in bench_by_case.get(case_id, [])}
        roles.discard("")
        if roles:
            cases_with_any_ref += 1
        for role in roles:
            role_coverage[role] += 1

    inventory = {
        "project_count": len(project_ids),
        "benchmark_relation_rows": len(bench),
        "cases_with_any_benchmark_role": cases_with_any_ref,
        "frozen_28_completed_tender_runs": sorted(frozen_28),
        "frozen_28_count": len(frozen_28),
        "remaining_without_frozen_tender_result": len(project_ids) - len(frozen_28),
        "full_352_bundle_present": bool(full_summary),
        "full_352_bundle_summary_keys": sorted(full_summary.keys()),
        "role_coverage_cases": dict(role_coverage),
        "expansion_status": "inputs_ready_tender_runs_not_executed",
        "blockers_for_claiming_352_complete": [
            "No full-352 tendering result archive under validation/full_352_cases/results/",
            "Running the remaining cases requires authorized LLM budget and a new task scope",
            "Closed-pool hit metrics for expanded cases still need size-matched baselines",
        ],
        "offline_ready_now": [
            "Candidate/project/enterprise CSVs for 352 cases",
            "Hidden benchmark relation table",
            "full_352_cases runner and config",
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "REPORT.md").write_text(
        "\n".join(
            [
                "# 352-case expansion eligibility",
                "",
                f"Projects: {inventory['project_count']}",
                f"Cases with any benchmark role: {inventory['cases_with_any_benchmark_role']}",
                f"Frozen tender runs: {inventory['frozen_28_count']}",
                f"Remaining without frozen tender result: {inventory['remaining_without_frozen_tender_result']}",
                "",
                f"Status: `{inventory['expansion_status']}`.",
                "",
                "Inputs and runner are present; full tender execution is not claimed complete.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"wrote {args.output_dir / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
