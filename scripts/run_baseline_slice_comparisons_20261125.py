#!/usr/bin/env python3
"""Stage-isolated external comparisons (Experiments 4–7).

Commands:
  prepare   Freeze protocol + cost estimate (no network).
  unpack    git lfs pull + unzip Experiment 1 full_run.zip checkpoints.
  dry-run   Materialize job cards from unpacked checkpoints (no network).
  status    Remaining jobs / checkpoint presence.
  run       Live or local engines. Dual gate required. Award/TOPSIS uses no API.
  score     Offline winner-agreement tables (award slice).

This is a NEW scoped experiment. Frozen micro-org and CP07 authorization files
are not launch credentials.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.baselines.award_topsis import compare_state
from src.baselines.historical_winners import annotate_winner_agreement, company_names, package_roles
from src.models import dump, load_simulation_state

EXP_ID = "baseline_slice_comparisons_20261125"
EXP = ROOT / "results/experiments" / EXP_ID
RUNS = ROOT / "runs" / EXP_ID
CHECKPOINTS = ROOT / "runs/baseline-checkpoints"
HIDDEN = ROOT / "data/test_sources/casebank_enterprise_matched/hidden_benchmark_project_enterprises.csv"

LIVE_ENV = "BASELINE_SLICE_ALLOW_LIVE"

SOURCES = {
    "micro-org-1118": ["CASE-0014", "CASE-0001", "CASE-0002", "CASE-0004", "CASE-0008", "CASE-0050"],
    "micro-org-replication-20261119": ["CASE-0253", "CASE-0271", "CASE-0319"],
    "micro-org-extension12-20261119": ["CASE-0145", "CASE-0089", "CASE-0202"],
}

SLICES = {
    "award": {
        "engines": ["topsis", "weighted_sum"],
        "stage_file": "stage_award.json",
        "llm": False,
        "experiment": 4,
    },
    "consortium": {
        "engines": ["llm_delib", "negmas"],
        "stage_file": "stage_bidders.json",
        "llm": True,
        "experiment": 5,
    },
    "intra": {
        "engines": ["marble_star", "marble_chain", "marble_graph"],
        "stage_file": "stage_bidders.json",
        "llm": True,
        "experiment": 6,
    },
    "biddoc": {
        "engines": ["bidgen"],
        "stage_file": "stage_bidders.json",
        "llm": True,
        "experiment": 7,
    },
}

# Frozen Experiment 1 multi-arm usage (three batches). Used only for PIC estimates.
HIST = {
    "multi_requests": 1749 + 798 + 761,
    "multi_input_tokens": 11_089_130 + 4_760_260 + 4_239_454,
    "multi_output_tokens": 1_177_845 + 508_215 + 445_865,
    "participation_units": 48 + 24 + 24,
    "submitted_bids": 40 + 17 + 19,
    "evaluation_award_units": 23 + 10 + 10,
    "judge_requests_per_3_projects": 675,
    "judge_input_tokens_per_3_projects": 3_196_166,
    "judge_output_tokens_per_3_projects": 370_597,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, obj, *, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and not overwrite:
        existing = path.read_text(encoding="utf-8")
        if existing != text:
            raise ValueError(f"Refuse to overwrite changed artifact: {path}")
        return
    path.write_text(text, encoding="utf-8")


def all_cases() -> list[tuple[str, str]]:
    return [(source, case_id) for source, cases in SOURCES.items() for case_id in cases]


def checkpoint_path(source: str, case_id: str, stage_file: str, arm: str = "multi") -> Path:
    return CHECKPOINTS / source / case_id / arm / stage_file


def zip_path(source: str) -> Path:
    return ROOT / "results/experiments" / source / "full_run.zip"


def is_lfs_pointer(path: Path) -> bool:
    if not path.exists() or path.stat().st_size > 500:
        return False
    head = path.read_text(encoding="utf-8", errors="replace")[:120]
    return head.startswith("version https://git-lfs.github.com/spec/v1")


def load_stage(source: str, case_id: str, stage_file: str):
    path = checkpoint_path(source, case_id, stage_file)
    payload = read_json(path)
    return load_simulation_state(payload["state"] if "state" in payload else payload)


def cost_estimate() -> dict:
    mean_in = HIST["multi_input_tokens"] / HIST["multi_requests"]
    mean_out = HIST["multi_output_tokens"] / HIST["multi_requests"]
    intra_calls = HIST["participation_units"] * 12 * 3
    consortium_floors = 20
    consortium_calls = consortium_floors * 24
    biddoc_calls = HIST["submitted_bids"] * 6
    judge_per_unit_in = HIST["judge_input_tokens_per_3_projects"] / 165
    judge_per_unit_out = HIST["judge_output_tokens_per_3_projects"] / 165
    judge_per_unit_req = HIST["judge_requests_per_3_projects"] / 165
    return {
        "experiment_id": EXP_ID,
        "basis": {
            "source": "Frozen Experiment 1 multi arm (micro-org-1118 + replication + extension12)",
            "multi_requests": HIST["multi_requests"],
            "mean_input_tokens_per_call": round(mean_in),
            "mean_output_tokens_per_call": round(mean_out),
            "note": "OrgBid multi artifacts are reused, not regenerated. Estimates are for the swapped engines plus new judging only.",
        },
        "slices": {
            "award": {
                "generation_calls": 0,
                "generation_input_tokens": 0,
                "generation_output_tokens": 0,
                "judge_calls": 0,
                "wall_clock": "minutes after unpack",
                "note": "TOPSIS / weighted sum are local. Historical winner column is post-hoc CSV, not a model call.",
            },
            "consortium": {
                "assumed_floors": consortium_floors,
                "generation_calls": {"llm_delib": consortium_calls, "negmas": 0},
                "generation_input_tokens": {"llm_delib": round(consortium_calls * mean_in), "negmas": 0},
                "generation_output_tokens": {"llm_delib": round(consortium_calls * mean_out), "negmas": 0},
                "note": "Floor count is an assumption until unpack+dry-run recounts bid_with_consortium rows. Recount replaces this row.",
            },
            "intra": {
                "tasks": HIST["participation_units"],
                "topologies": 3,
                "calls_per_task_matched_to_orgbid_multi": 12,
                "generation_calls": intra_calls,
                "generation_input_tokens": round(intra_calls * mean_in),
                "generation_output_tokens": round(intra_calls * mean_out),
                "judge_calls": round(HIST["participation_units"] * 3 * judge_per_unit_req),
                "judge_input_tokens": round(HIST["participation_units"] * 3 * judge_per_unit_in),
                "judge_output_tokens": round(HIST["participation_units"] * 3 * judge_per_unit_out),
            },
            "biddoc": {
                "submitted_bids_in_frozen_multi": HIST["submitted_bids"],
                "calls_per_document": 6,
                "generation_calls": biddoc_calls,
                "generation_input_tokens": round(biddoc_calls * mean_in),
                "generation_output_tokens": round(biddoc_calls * mean_out),
                "judge_calls": round(HIST["submitted_bids"] * judge_per_unit_req),
                "judge_input_tokens": round(HIST["submitted_bids"] * judge_per_unit_in),
                "judge_output_tokens": round(HIST["submitted_bids"] * judge_per_unit_out),
            },
        },
        "recommended_first_spend": {
            "slice": "award",
            "generation_calls": 0,
            "purpose": "Prove the harness on frozen opened bids before any paid engine.",
        },
        "smoke": {
            "case": "CASE-0014",
            "award_calls": 0,
            "intra_marble_star_calls": 8 * 12,
            "intra_input_tokens": round(8 * 12 * mean_in),
            "intra_output_tokens": round(8 * 12 * mean_out),
        },
        "money": {
            "currency_note": "Do not use this file as a quote. Price from the current DeepSeek / provider dashboard using the token counts above.",
            "model": "deepseek-flash",
            "scale_from_experiment_1": "Experiment 1 reported at most about CNY 83 list-price for all three OrgBid arms on 12 projects. New LLM slices are additional and are not covered by that figure.",
        },
    }


def protocol_payload() -> dict:
    jobs = []
    for slice_name, spec in SLICES.items():
        for engine in spec["engines"]:
            for source, case_id in all_cases():
                jobs.append({
                    "job_id": f"{slice_name}__{engine}__{source}__{case_id}",
                    "slice": slice_name,
                    "engine": engine,
                    "source": source,
                    "case_id": case_id,
                    "stage_file": spec["stage_file"],
                    "uses_llm": spec["llm"] and engine not in {"topsis", "weighted_sum", "negmas"},
                    "experiment": spec["experiment"],
                })
    return {
        "experiment_id": EXP_ID,
        "created_at_UTC": "2026-11-25T00:00:00+00:00",
        "design": {
            "stage_isolated": True,
            "reference_arm": "multi",
            "hidden_labels_withheld_from_engines": True,
            "historical_auth_is_not_launch_credential": True,
            "do_not_overwrite_frozen_micro_org": True,
            "one_engine_per_run": True,
        },
        "cases": SOURCES,
        "slices": {name: {k: v for k, v in spec.items()} for name, spec in SLICES.items()},
        "jobs": jobs,
        "n_jobs": len(jobs),
        "live_gate": {
            "env": LIVE_ENV,
            "flag": "--i-authorize-live-calls",
        },
        "paths": {
            "checkpoints": str(CHECKPOINTS.relative_to(ROOT)),
            "runs": str(RUNS.relative_to(ROOT)),
            "hidden_benchmark": str(HIDDEN.relative_to(ROOT)),
            "full_run_zip": f"results/experiments/{EXP_ID}/full_run.zip",
        },
    }


def cmd_prepare(_args) -> None:
    EXP.mkdir(parents=True, exist_ok=True)
    write_json(EXP / "protocol.json", protocol_payload(), overwrite=False)
    write_json(EXP / "cost_estimate.json", cost_estimate(), overwrite=False)
    write_json(
        EXP / "index.json",
        {
            "experiment_id": EXP_ID,
            "status": "protocol_frozen; live engines other than award/topsis not yet implemented",
            "readme": "README.md",
            "spec": "research/references/baseline_comparison_implementation_spec.md",
            "paper": "research/paper/external_comparison_experiments.md",
        },
        overwrite=False,
    )
    print(json.dumps({"prepared": str(EXP), "jobs": protocol_payload()["n_jobs"]}, ensure_ascii=False))


def cmd_unpack(_args) -> None:
    missing = [source for source in SOURCES if not zip_path(source).exists()]
    if missing:
        raise SystemExit(f"Missing Experiment 1 archives: {missing}")
    pointers = [source for source in SOURCES if is_lfs_pointer(zip_path(source))]
    if pointers:
        include = ",".join(f"results/experiments/{source}/full_run.zip" for source in pointers)
        print(f"git lfs pull --include '{include}'", flush=True)
        result = subprocess.run(["git", "lfs", "pull", "--include", include], cwd=ROOT)
        if result.returncode != 0:
            raise SystemExit(
                "git lfs pull failed. Install Git LFS, then re-run unpack. "
                "Pointer files are 133 bytes and cannot be unzipped."
            )
        still = [source for source in pointers if is_lfs_pointer(zip_path(source))]
        if still:
            raise SystemExit(f"Still LFS pointers after pull: {still}")
    for source in SOURCES:
        target = CHECKPOINTS / source
        target.mkdir(parents=True, exist_ok=True)
        marker = target / ".unpacked.json"
        archive = zip_path(source)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(target)
        write_json(
            marker,
            {"source": source, "archive": str(archive.relative_to(ROOT)), "unpacked_at": utc_now(),
             "files": len(list(target.rglob("*")))},
            overwrite=True,
        )
        print(json.dumps({"unpacked": source, "dest": str(target)}, ensure_ascii=False))


def job_dir(job: dict) -> Path:
    return RUNS / job["slice"] / job["engine"] / job["source"] / job["case_id"]


def materialize_job(job: dict) -> dict:
    stage = checkpoint_path(job["source"], job["case_id"], job["stage_file"])
    card = {
        **job,
        "checkpoint": str(stage.relative_to(ROOT)) if stage.exists() else None,
        "checkpoint_present": stage.exists(),
        "status": "ready" if stage.exists() else "waiting_for_checkpoint",
    }
    if stage.exists() and job["slice"] == "award":
        state = load_stage(job["source"], job["case_id"], job["stage_file"])
        card["n_packages"] = len(state.tender_packages)
        card["n_bids"] = len(state.bid_documents)
        card["n_orgbid_awards"] = sum(
            1 for report in state.evaluation_report if report.recommended_winner
        )
    if stage.exists() and job["slice"] == "consortium":
        state = load_stage(job["source"], job["case_id"], job["stage_file"])
        card["n_consortium_requests"] = sum(
            1 for item in state.participation_decisions if item.decision == "bid_with_consortium"
        )
        card["n_formed_orgbid"] = sum(1 for item in state.consortiums if item.status == "formed")
    if stage.exists() and job["slice"] == "intra":
        state = load_stage(job["source"], job["case_id"], job["stage_file"])
        card["n_participation"] = len(state.participation_decisions)
    if stage.exists() and job["slice"] == "biddoc":
        state = load_stage(job["source"], job["case_id"], job["stage_file"])
        card["n_submitted_bids"] = len(state.bid_documents)
    dest = job_dir(job)
    write_json(dest / "job.json", card, overwrite=True)
    return card


def cmd_dry_run(args) -> None:
    protocol = read_json(EXP / "protocol.json")
    selected = [
        job for job in protocol["jobs"]
        if (not args.slice or job["slice"] == args.slice)
        and (not args.engine or job["engine"] == args.engine)
        and (not args.case or job["case_id"] == args.case)
    ]
    cards = [materialize_job(job) for job in selected]
    ledger = {
        "written_at": utc_now(),
        "n": len(cards),
        "ready": sum(1 for card in cards if card["status"] == "ready"),
        "waiting_for_checkpoint": sum(1 for card in cards if card["status"] == "waiting_for_checkpoint"),
        "jobs": cards,
    }
    write_json(RUNS / "dry_run_ledger.json", ledger, overwrite=True)
    print(json.dumps({k: ledger[k] for k in ("n", "ready", "waiting_for_checkpoint")}, ensure_ascii=False))
    if ledger["waiting_for_checkpoint"]:
        print("Run unpack before live award scoring: python3 scripts/run_baseline_slice_comparisons_20261125.py unpack")


def cmd_status(_args) -> None:
    protocol = read_json(EXP / "protocol.json")
    rows = []
    for job in protocol["jobs"]:
        dest = job_dir(job)
        rows.append({
            "job_id": job["job_id"],
            "checkpoint": checkpoint_path(job["source"], job["case_id"], job["stage_file"]).exists(),
            "job_card": (dest / "job.json").exists(),
            "result": (dest / "result.json").exists(),
        })
    print(json.dumps({
        "checkpoints_ready": sum(1 for row in rows if row["checkpoint"]),
        "job_cards": sum(1 for row in rows if row["job_card"]),
        "results": sum(1 for row in rows if row["result"]),
        "n_jobs": len(rows),
        "lfs_pointers": [source for source in SOURCES if is_lfs_pointer(zip_path(source))],
    }, ensure_ascii=False, indent=2))


def refuse_live() -> None:
    raise SystemExit(
        "Refusing live calls. Set "
        f"{LIVE_ENV}=1 and pass --i-authorize-live-calls. "
        "Frozen micro-org / CP07 authorization files are not credentials for this experiment."
    )


def implemented(engine: str) -> bool:
    if engine in {"topsis", "weighted_sum"}:
        return True
    mapping = {
        "llm_delib": "src.baselines.consortium_llm_delib",
        "negmas": "src.baselines.consortium_negmas",
        "marble_star": "src.baselines.intra_marble",
        "marble_chain": "src.baselines.intra_marble",
        "marble_graph": "src.baselines.intra_marble",
        "bidgen": "src.baselines.bidgen_writer",
    }
    module_name = mapping.get(engine)
    if not module_name:
        return False
    module = __import__(module_name, fromlist=["IMPLEMENTED"])
    return bool(getattr(module, "IMPLEMENTED", False))


def run_award_job(job: dict) -> dict:
    state = load_stage(job["source"], job["case_id"], job["stage_file"])
    weight_mode = "entropy" if job["engine"] == "topsis" and os.getenv("BASELINE_TOPSIS_WEIGHTS") == "entropy" else "equal"
    if job["engine"] == "weighted_sum":
        from src.baselines.award_topsis import weighted_sum_rank, evaluation_from_ranking, award_from_ranking, kendall_tau, orgbid_rank
        rows = []
        for package in state.tender_packages:
            ranked = weighted_sum_rank(state, package.package_id)
            org_order = orgbid_rank(state, package.package_id)
            num_order = [item.bidder_id for item in ranked]
            org_winner = next((report.recommended_winner for report in state.evaluation_report if report.package_id == package.package_id), None)
            num_winner = ranked[0].bidder_id if ranked else None
            rows.append({
                "package_id": package.package_id,
                "weight_mode": "weighted_sum",
                "orgbid_winner": org_winner,
                "numerical_winner": num_winner,
                "winner_agreement": bool(org_winner) and org_winner == num_winner,
                "n_admissible": len(ranked),
                "kendall_tau": kendall_tau(org_order, num_order),
                "orgbid_order": org_order,
                "numerical_order": num_order,
                "evaluation_report": dump(evaluation_from_ranking(package.package_id, ranked)),
                "award_result": dump(award_from_ranking(package.package_id, ranked)),
            })
    else:
        rows = compare_state(state, weight_mode=weight_mode)
    annotated = annotate_winner_agreement(
        rows,
        case_id=job["case_id"],
        role_by_package=package_roles(state),
        company_name_by_id=company_names(state),
        hidden_path=HIDDEN,
    )
    return {
        "job_id": job["job_id"],
        "status": "done",
        "engine": job["engine"],
        "n_packages": len(annotated),
        "winner_agreements": sum(1 for row in annotated if row["winner_agreement"]),
        "packages": annotated,
        "tokens": {"requests": 0, "input_tokens": 0, "output_tokens": 0},
        "finished_at": utc_now(),
    }


def cmd_run(args) -> None:
    if not args.i_authorize_live_calls or os.getenv(LIVE_ENV) != "1":
        refuse_live()
    protocol = read_json(EXP / "protocol.json")
    selected = [
        job for job in protocol["jobs"]
        if (not args.slice or job["slice"] == args.slice)
        and (not args.engine or job["engine"] == args.engine)
        and (not args.case or job["case_id"] == args.case)
    ]
    remaining = args.max_calls
    done = 0
    for job in selected:
        if remaining is not None and remaining <= 0:
            break
        dest = job_dir(job)
        result_path = dest / "result.json"
        if result_path.exists() and not args.force:
            done += 1
            continue
        if not checkpoint_path(job["source"], job["case_id"], job["stage_file"]).exists():
            raise SystemExit(f"Missing checkpoint for {job['job_id']}; run unpack then dry-run.")
        if not implemented(job["engine"]):
            raise SystemExit(
                f"Engine {job['engine']!r} is specified but not implemented. "
                "Award/topsis and award/weighted_sum are the only engines that run in this commit. "
                "See research/references/baseline_comparison_implementation_spec.md"
            )
        if job["slice"] != "award":
            raise SystemExit(f"Slice {job['slice']} is not runnable in this commit.")
        result = run_award_job(job)
        write_json(result_path, result, overwrite=True)
        done += 1
        if remaining is not None:
            remaining -= 1
        print(json.dumps({"job_id": job["job_id"], "status": "done", "agreements": result["winner_agreements"]}, ensure_ascii=False), flush=True)
    print(json.dumps({"finished_jobs": done}, ensure_ascii=False))


def cmd_score(args) -> None:
    protocol = read_json(EXP / "protocol.json")
    rows = []
    for job in protocol["jobs"]:
        if job["slice"] != "award":
            continue
        if args.engine and job["engine"] != args.engine:
            continue
        path = job_dir(job) / "result.json"
        if not path.exists():
            continue
        payload = read_json(path)
        for package in payload.get("packages", []):
            rows.append({"case_id": job["case_id"], "engine": job["engine"], **package})
    comparable = [row for row in rows if row.get("historical_comparable")]
    summary = {
        "n_packages": len(rows),
        "winner_agreement_rate": (sum(1 for row in rows if row.get("winner_agreement")) / len(rows)) if rows else None,
        "n_historically_comparable": len(comparable),
        "orgbid_history_hit": (sum(1 for row in comparable if row.get("orgbid_matches_history")) / len(comparable)) if comparable else None,
        "numerical_history_hit": (sum(1 for row in comparable if row.get("numerical_matches_history")) / len(comparable)) if comparable else None,
        "mean_kendall_tau": (
            sum(row["kendall_tau"] for row in rows if row.get("kendall_tau") is not None)
            / max(1, sum(1 for row in rows if row.get("kendall_tau") is not None))
        ) if any(row.get("kendall_tau") is not None for row in rows) else None,
    }
    dest = EXP / "summaries"
    write_json(dest / "award_score.json", {"summary": summary, "packages": rows}, overwrite=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    sub.add_parser("unpack")
    dry = sub.add_parser("dry-run")
    dry.add_argument("--slice", choices=list(SLICES))
    dry.add_argument("--engine")
    dry.add_argument("--case")
    sub.add_parser("status")
    run = sub.add_parser("run")
    run.add_argument("--i-authorize-live-calls", action="store_true")
    run.add_argument("--slice", choices=list(SLICES))
    run.add_argument("--engine")
    run.add_argument("--case")
    run.add_argument("--max-calls", type=int, default=None)
    run.add_argument("--force", action="store_true")
    score = sub.add_parser("score")
    score.add_argument("--engine", default="topsis")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    commands = {
        "prepare": cmd_prepare,
        "unpack": cmd_unpack,
        "dry-run": cmd_dry_run,
        "status": cmd_status,
        "run": cmd_run,
        "score": cmd_score,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
