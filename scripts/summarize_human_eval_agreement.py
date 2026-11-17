#!/usr/bin/env python3
"""Compute percent agreement and Cohen's kappa from completed human score sheets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.tender_metrics.human_eval import summarize_rater_pair  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheets-dir", type=Path, required=True)
    parser.add_argument("--rater-a", default="raterA")
    parser.add_argument("--rater-b", default="raterB")
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sheets_a = []
    sheets_b = []
    for path in sorted(args.sheets_dir.glob("*.json")):
        sheet = json.loads(path.read_text(encoding="utf-8"))
        if sheet.get("rater_id") == args.rater_a:
            sheets_a.append(sheet)
        elif sheet.get("rater_id") == args.rater_b:
            sheets_b.append(sheet)
    summary = summarize_rater_pair(sheets_a, sheets_b)
    completed = sum(
        1
        for sheet in sheets_a + sheets_b
        if all(value is not None for value in sheet.get("scores", {}).values())
    )
    summary["completed_sheets"] = completed
    summary["rater_a_sheets"] = len(sheets_a)
    summary["rater_b_sheets"] = len(sheets_b)
    text = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(args.output)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
