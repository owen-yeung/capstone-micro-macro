#!/usr/bin/env python3
"""Build blinded human behavioral-plausibility packets from the frozen 28-case archive.

Offline only. Creates rubric blanks and de-identified excerpts; does not score them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.tender_metrics.human_eval import DIMENSIONS, RUBRIC_VERSION, blank_score_sheet  # noqa: E402

DEFAULT_CASES = ROOT / "validation/benchmark_ge3_compact/results/final_28_20260817/cases"
DEFAULT_OUT = ROOT / "results/experiments/interim_6_2_offline_20261117/human_eval_packets"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases-root", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-packages", type=int, default=24, help="Sample size for the first human round.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packets_dir = args.output_dir / "packets"
    sheets_dir = args.output_dir / "score_sheets_blank"
    packets_dir.mkdir(parents=True, exist_ok=True)
    sheets_dir.mkdir(parents=True, exist_ok=True)
    index = []
    count = 0
    for case_dir in sorted(path for path in args.cases_root.iterdir() if path.is_dir()):
        case_id = f"CASE-{case_dir.name.split('-', 1)[1]}"
        award = json.loads((case_dir / "simulated_award_result.json").read_text(encoding="utf-8"))
        discussion = json.loads((case_dir / "agent_discussion_history.json").read_text(encoding="utf-8"))
        for package in award.get("package_awards", []):
            if count >= args.max_packages:
                break
            package_id = package["package_id"]
            packet_id = f"{case_id}__{package_id}"
            packet = {
                "packet_id": packet_id,
                "rubric_version": RUBRIC_VERSION,
                "dimensions": DIMENSIONS,
                "blinded": True,
                "case_label": f"PACKET-{count + 1:03d}",
                "package_role_hint": package_id.replace("_package", ""),
                "award_excerpt": {
                    "bidder_type": package.get("bidder_type"),
                    "decision_reason": package.get("decision_reason"),
                },
                "discussion_excerpts": _discussion_excerpts(discussion, package_id),
                "source_paths_hidden_from_rater": [
                    str(case_dir / "simulated_award_result.json"),
                    str(case_dir / "agent_discussion_history.json"),
                    str(case_dir / "bid_documents.json"),
                ],
                "instructions": (
                    "Score BP1–BP5 using only this packet. Do not look up case ids, company names "
                    "outside the packet, or benchmark outcomes."
                ),
            }
            packet_path = packets_dir / f"{packet_id}.json"
            sheet_path = sheets_dir / f"{packet_id}__raterA.json"
            packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            sheet = blank_score_sheet(
                case_id=case_id,
                package_id=package_id,
                rater_id="raterA",
                artifact_paths=[str(packet_path.relative_to(ROOT))],
            )
            sheet["packet_id"] = packet_id
            sheet_path.write_text(json.dumps(sheet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            # Second blank for IRR.
            sheet_b = dict(sheet)
            sheet_b["rater_id"] = "raterB"
            (sheets_dir / f"{packet_id}__raterB.json").write_text(
                json.dumps(sheet_b, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            index.append({"packet_id": packet_id, "case_id": case_id, "package_id": package_id})
            count += 1
        if count >= args.max_packages:
            break
    manifest = {
        "rubric_version": RUBRIC_VERSION,
        "packet_count": len(index),
        "packets": index,
        "status": "blanks_ready_awaiting_human_ratings",
        "note": "No ratings are filled. IRR requires independent human completion of raterA/raterB sheets.",
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "README.md").write_text(
        "\n".join(
            [
                "# Human behavioral plausibility packets",
                "",
                f"Rubric `{RUBRIC_VERSION}` with dimensions BP1–BP5.",
                f"Built {len(index)} blinded packets from the frozen 28-case archive.",
                "Fill `score_sheets_blank/*__raterA.json` and `*__raterB.json`, then run",
                "`scripts/summarize_human_eval_agreement.py`.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"packets={len(index)} output={args.output_dir}")
    return 0


def _discussion_excerpts(discussion: list[dict], package_id: str, limit: int = 8) -> list[dict]:
    rows = [
        {
            "stage": item.get("stage"),
            "round": item.get("round"),
            "role": item.get("company_role"),
            "message_type": item.get("message_type"),
            "content": item.get("content") or item.get("message") or item.get("text") or "",
        }
        for item in discussion
        if item.get("package_id") == package_id
    ]
    # Prefer formation / reconsideration / bid stages when present.
    preferred = [
        row
        for row in rows
        if row["stage"]
        in {
            "bid_participation_decision",
            "consortium_formation",
            "consortium_failure_reconsideration",
            "bid_document_generation",
            "evaluation",
            "owner_award_decision",
        }
    ]
    chosen = preferred or rows
    return [
        {
            **row,
            "content": (row["content"][:500] + ("…" if len(row["content"]) > 500 else "")),
        }
        for row in chosen[:limit]
    ]


if __name__ == "__main__":
    raise SystemExit(main())
