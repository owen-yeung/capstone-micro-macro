#!/usr/bin/env python3
"""Pre-registered D3/S4 ablation + input-sensitivity experiment runner.

Commands:
  prepare   Freeze sample, ablation plan, cost estimate (no network).
  dry-run   Materialize every request JSON under runs/… (no network).
  status    Show ledger / remaining jobs.
  run       Live model calls (requires explicit authorization flags + env).

This is a NEW scoped experiment. Historical CP07 authorization.json is NOT
a launch credential. Default paths never overwrite frozen business_review.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

CP07 = ROOT / "Capstone报告/验证体系/实验/2026-11-13_CP07组织质量对照"
REV = ROOT / "Capstone报告/验证体系/实验/2026-11-13_总实验收尾/business_review/CP07"
EXP = ROOT / "results/experiments/org_ablation_sensitivity_20261119"
RUNS = ROOT / "runs/org_ablation_sensitivity_20261119"

SEED = "org-ablation-20261119"
N_PER_ROLE = 2
MODEL_DEFAULT = "deepseek-flash"
TEMPERATURE = 0.2
MAX_COMPLETION = 4096
CONCURRENCY_DEFAULT = 2

# Final-only ablations (mutate frozen CP07 request-step-4 prompts).
ABLATION_KINDS = [
    "dropout_step1",
    "dropout_step2",
    "dropout_step3",
    "order_perm_021",  # steps reordered 0,2,1
    "order_perm_102",  # 1,0,2
    "bitflip_gate_D3",
    "bitflip_gate_S4",
]

# Historical CP07 step-4 usage (continuation jobs), used for PIC estimates.
HIST_STEP4_MEAN_TOTAL_TOKENS = 5675
HIST_STEP4_MEDIAN_SECONDS = 6.35


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, obj, *, overwrite: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and not overwrite:
        if path.read_text(encoding="utf-8") != text:
            raise ValueError(f"Refuse to overwrite changed artifact: {path}")
        return
    path.write_text(text, encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def find_job(window: str, arm: str) -> Path | None:
    name = f"{window}-{arm}-r1"
    for cont in ("continuation-002", "continuation-001", "run"):
        for base in (CP07 / cont / "run" / "jobs", CP07 / "run" / "jobs"):
            p = base / name
            if (p / "request-step-4.json").exists() and (p / "step-1.json").exists():
                return p
    return None


def load_grades_index():
    by = {}
    for f in sorted(REV.glob("*.json")):
        d = read_json(f)
        by.setdefault(d["window_id"], {})[d["arm"]] = {
            "role": d["role"],
            "project_group": d["project_group"],
            "annotated_action": d.get("annotated_action"),
            "D1": (d.get("D1") or {}).get("label"),
            "D2": d.get("D2_correct_coverage"),
            "grade_path": str(f.relative_to(ROOT)).replace("\\", "/"),
        }
    return by


def select_windows(by: dict) -> list[dict]:
    selected = []
    for role in ("contractor", "supplier", "designer", "supervisor"):
        pool = []
        for window, arms in by.items():
            if arms.get("D3", {}).get("role") != role:
                continue
            if not {"D3", "S4"} <= set(arms):
                continue
            if find_job(window, "D3") and find_job(window, "S4"):
                pool.append(window)
        ranked = sorted(pool, key=lambda w: hashlib.sha256(f"{SEED}|{w}".encode()).hexdigest())
        for window in ranked[:N_PER_ROLE]:
            selected.append(
                {
                    "window_id": window,
                    "role": role,
                    "info": "missing_core" if "missing" in window else "full",
                    "selection_key": f"{SEED}|{window}",
                    "selection_sha256": hashlib.sha256(f"{SEED}|{window}".encode()).hexdigest(),
                    "d3_job": str(find_job(window, "D3").relative_to(ROOT)).replace("\\", "/"),
                    "s4_job": str(find_job(window, "S4").relative_to(ROOT)).replace("\\", "/"),
                    "frozen_grades": {
                        "D3": by[window]["D3"],
                        "S4": by[window]["S4"],
                    },
                }
            )
    return selected


def extract_internal_proposals(messages: list) -> tuple[int, list]:
    for i, msg in enumerate(messages):
        content = msg.get("content") or ""
        if content.startswith("INTERNAL_PROPOSALS_NOT_EXTERNAL_RECEIPTS:"):
            payload = content.split(":", 1)[1].strip()
            return i, json.loads(payload)
    raise ValueError("INTERNAL_PROPOSALS block not found in request-step-4")


def set_internal_proposals(messages: list, index: int, proposals: list):
    messages[index] = {
        "role": "user",
        "content": "INTERNAL_PROPOSALS_NOT_EXTERNAL_RECEIPTS:\n"
        + json.dumps(proposals, ensure_ascii=False),
    }


def load_step_comments(job: Path) -> list[dict]:
    rows = []
    for step in (1, 2, 3):
        d = read_json(job / f"step-{step}.json")
        rows.append(
            {
                "step": step,
                "position": d.get("position"),
                "comment": d.get("public_comment") or "",
            }
        )
    if any(not r["comment"] for r in rows):
        raise ValueError(f"Missing process comments in {job}")
    return rows


def pick_gate_condition(request: dict) -> dict:
    """Pick a material gate bit from the frozen final prompt text."""
    blob = "\n".join(m.get("content") or "" for m in request["messages"])
    # Prefer staffing/档期 gates; else first unresolved condition id.
    m = re.search(
        r'"condition_id"\s*:\s*"(condition_[0-9a-f]+)"[^}]*?"question"\s*:\s*"([^"]*档期[^"]*)"',
        blob,
    )
    if m:
        return {
            "condition_id": m.group(1),
            "question": m.group(2),
            "flip_kind": "mark_staffing_gate_verified",
        }
    m = re.search(r'"unresolved_condition_ids"\s*:\s*\[\s*"(condition_[0-9a-f]+)"', blob)
    if m:
        return {
            "condition_id": m.group(1),
            "question": None,
            "flip_kind": "mark_first_unresolved_verified",
        }
    return {
        "condition_id": None,
        "question": None,
        "flip_kind": "inject_synthetic_verified_staffing_note",
    }


def bitflip_message(spec: dict) -> dict:
    if spec["flip_kind"] == "mark_staffing_gate_verified":
        text = (
            "ABLATION_BITFLIP (pre-registered material input change): "
            f"Host now marks {spec['condition_id']} as verified for this controlled replay. "
            f"Question was: {spec['question']}. "
            "Treat the staffing/schedule gate as satisfied with scoped host evidence. "
            "Do not invent other new facts. Update the final intention/document accordingly."
        )
    elif spec["flip_kind"] == "mark_first_unresolved_verified":
        text = (
            "ABLATION_BITFLIP (pre-registered material input change): "
            f"Host now marks {spec['condition_id']} as verified for this controlled replay. "
            "Keep all other unresolved conditions unchanged. Update the final accordingly."
        )
    else:
        text = (
            "ABLATION_BITFLIP (pre-registered material input change): "
            "Host injects a scoped verification that the package-designated post staffing schedule "
            "is available for submission. Do not invent other capabilities. Update the final accordingly."
        )
    return {"role": "user", "content": text}


def build_ablation_request(window_row: dict, kind: str) -> dict:
    if kind.startswith("bitflip_gate_"):
        arm = "D3" if kind.endswith("D3") else "S4"
        job = ROOT / window_row["d3_job" if arm == "D3" else "s4_job"]
        req = deepcopy(read_json(job / "request-step-4.json"))
        spec = pick_gate_condition(req)
        # Insert bitflip just before FINAL_ANSWER message.
        messages = req["messages"]
        insert_at = len(messages) - 1
        for i, msg in enumerate(messages):
            if (msg.get("content") or "").startswith("FINAL_ANSWER"):
                insert_at = i
                break
        messages.insert(insert_at, bitflip_message(spec))
        req["messages"] = messages
        req["ablation"] = {
            "kind": kind,
            "arm": arm,
            "window_id": window_row["window_id"],
            "bitflip": spec,
            "source_request": str((job / "request-step-4.json").relative_to(ROOT)).replace("\\", "/"),
        }
        return req

    # Dropout / order: D3 finals only, mutate internal proposals.
    job = ROOT / window_row["d3_job"]
    req = deepcopy(read_json(job / "request-step-4.json"))
    idx, proposals = extract_internal_proposals(req["messages"])
    if len(proposals) != 3:
        raise ValueError(f"Expected 3 D3 proposals, got {len(proposals)} for {job}")

    if kind.startswith("dropout_step"):
        drop = int(kind.replace("dropout_step", ""))
        new_props = [p for p in proposals if int(p.get("step", 0)) != drop]
        if len(new_props) != 2:
            # fall back to positional drop
            new_props = [p for i, p in enumerate(proposals, 1) if i != drop]
        set_internal_proposals(req["messages"], idx, new_props)
        detail = {"dropped_step": drop, "remaining_steps": [p.get("step") for p in new_props]}
    elif kind == "order_perm_021":
        order = [0, 2, 1]
        new_props = [deepcopy(proposals[i]) for i in order]
        for i, p in enumerate(new_props, 1):
            p["step"] = i
        set_internal_proposals(req["messages"], idx, new_props)
        detail = {"permutation": order}
    elif kind == "order_perm_102":
        order = [1, 0, 2]
        new_props = [deepcopy(proposals[i]) for i in order]
        for i, p in enumerate(new_props, 1):
            p["step"] = i
        set_internal_proposals(req["messages"], idx, new_props)
        detail = {"permutation": order}
    else:
        raise ValueError(kind)

    req["ablation"] = {
        "kind": kind,
        "arm": "D3",
        "window_id": window_row["window_id"],
        "detail": detail,
        "source_request": str((job / "request-step-4.json").relative_to(ROOT)).replace("\\", "/"),
    }
    return req


def job_id(window_id: str, kind: str) -> str:
    return f"{window_id}__{kind}"


def estimate_budget(n_jobs: int) -> dict:
    tokens = n_jobs * HIST_STEP4_MEAN_TOTAL_TOKENS
    # concurrency 2
    wall_min = (n_jobs / CONCURRENCY_DEFAULT) * HIST_STEP4_MEDIAN_SECONDS / 60.0
    return {
        "n_jobs": n_jobs,
        "calls_per_job": 1,
        "total_calls": n_jobs,
        "hist_basis": {
            "cp07_step4_mean_total_tokens": HIST_STEP4_MEAN_TOTAL_TOKENS,
            "cp07_step4_median_seconds": HIST_STEP4_MEDIAN_SECONDS,
            "note": "Estimated from frozen CP07 step-4 usage_metadata across ~317 finals.",
        },
        "estimated_total_tokens": tokens,
        "estimated_wall_clock_minutes_concurrency_2": round(wall_min, 1),
        "estimated_wall_clock_minutes_with_overhead": {
            "optimistic": round(wall_min * 1.5, 1),
            "likely": round(max(15.0, wall_min * 3.0), 1),
            "pessimistic_rate_limits": round(max(30.0, wall_min * 6.0), 1),
        },
        "relative_to_cp07": {
            "cp07_planned_calls": 864,
            "this_experiment_calls": n_jobs,
            "call_fraction_of_cp07": round(n_jobs / 864, 3),
            "approx_d3_job_equivalents_by_tokens": round(tokens / 19134, 1),
        },
        "money": {
            "currency_note": "DeepSeek flash list prices change; PIC should price from current provider dashboard.",
            "inputs_for_quote": {
                "estimated_total_tokens": tokens,
                "model": MODEL_DEFAULT,
                "approx_split": "historically ~77% input / ~23% output on CP07 finals",
            },
        },
    }


def cmd_prepare(overwrite: bool = False):
    by = load_grades_index()
    windows = select_windows(by)
    jobs = []
    for w in windows:
        for kind in ABLATION_KINDS:
            jobs.append(
                {
                    "job_id": job_id(w["window_id"], kind),
                    "window_id": w["window_id"],
                    "ablation_kind": kind,
                    "calls": 1,
                    "arm": "S4" if kind.endswith("S4") else "D3",
                }
            )
    protocol = {
        "experiment_id": "org_ablation_sensitivity_20261119",
        "seed_string": SEED,
        "created_at_UTC": datetime.now(timezone.utc).isoformat(),
        "model": MODEL_DEFAULT,
        "temperature": TEMPERATURE,
        "max_completion_tokens": MAX_COMPLETION,
        "concurrency": CONCURRENCY_DEFAULT,
        "design": {
            "n_windows": len(windows),
            "n_per_role": N_PER_ROLE,
            "ablation_kinds": ABLATION_KINDS,
            "call_pattern": "final_only_on_frozen_CP07_request_step_4_with_mutated_history_or_bitflip",
            "primary_endpoints": [
                "annotated_action_or_structural_flip_vs_frozen_final",
                "dropout_quality_delta_proxy",
                "order_agreement_across_permutations",
                "bitflip_directed_change_rate_D3_vs_S4",
            ],
            "does_not_overwrite_frozen_grades": True,
            "historical_cp07_auth_is_not_launch_credential": True,
        },
        "windows": windows,
        "jobs": jobs,
        "max_calls": len(jobs),
        "cost_estimate": estimate_budget(len(jobs)),
    }
    write_json(EXP / "protocol.json", protocol, overwrite=overwrite)
    write_json(
        EXP / "sample_manifest.json",
        {"seed": SEED, "windows": [w["window_id"] for w in windows], "jobs": len(jobs)},
        overwrite=overwrite,
    )
    write_json(EXP / "cost_estimate.json", protocol["cost_estimate"], overwrite=overwrite)
    write_json(
        EXP / "index.json",
        {
            "experiment_id": "org_ablation_sensitivity_20261119",
            "commands": [
                "python3 scripts/run_org_ablation_sensitivity_20261119.py prepare",
                "python3 scripts/run_org_ablation_sensitivity_20261119.py dry-run",
                "python3 scripts/run_org_ablation_sensitivity_20261119.py run --i-authorize-live-calls --max-calls 56",
            ],
            "readme": "README.md",
            "protocol": "protocol.json",
        },
        overwrite=overwrite,
    )
    print(
        json.dumps(
            {
                "prepared": True,
                "windows": len(windows),
                "jobs": len(jobs),
                "max_calls": len(jobs),
                "estimate_tokens": protocol["cost_estimate"]["estimated_total_tokens"],
                "out": str(EXP.relative_to(ROOT)),
            },
            indent=2,
        )
    )


def load_protocol() -> dict:
    path = EXP / "protocol.json"
    if not path.exists():
        raise SystemExit("Missing protocol.json — run: prepare")
    return read_json(path)


def cmd_dry_run():
    protocol = load_protocol()
    by_window = {w["window_id"]: w for w in protocol["windows"]}
    ledger = {
        "at_UTC": datetime.now(timezone.utc).isoformat(),
        "mode": "dry-run",
        "jobs": [],
    }
    for job in protocol["jobs"]:
        window = by_window[job["window_id"]]
        req = build_ablation_request(window, job["ablation_kind"])
        folder = RUNS / "dry-run" / job["job_id"]
        write_json(folder / "request.json", req, overwrite=True)
        meta = {
            "job": job,
            "prompt_sha256": sha256_bytes(
                json.dumps(req["messages"], ensure_ascii=False, sort_keys=True).encode()
            ),
            "ablation": req["ablation"],
            "status": "request_materialized_no_provider_call",
        }
        write_json(folder / "job_meta.json", meta, overwrite=True)
        ledger["jobs"].append(
            {
                "job_id": job["job_id"],
                "status": meta["status"],
                "prompt_sha256": meta["prompt_sha256"],
                "path": str(folder.relative_to(ROOT)).replace("\\", "/"),
            }
        )
    write_json(RUNS / "dry-run" / "ledger.json", ledger, overwrite=True)
    write_json(EXP / "dry_run_ledger.json", ledger, overwrite=True)
    print(
        json.dumps(
            {
                "dry_run": True,
                "jobs": len(ledger["jobs"]),
                "runs_dir": str((RUNS / "dry-run").relative_to(ROOT)),
                "network": False,
            },
            indent=2,
        )
    )


def cmd_status():
    protocol = load_protocol()
    live_ledger = RUNS / "live" / "ledger.json"
    done = set()
    if live_ledger.exists():
        for row in read_json(live_ledger).get("jobs", []):
            if row.get("status") in {"returned", "succeeded"}:
                done.add(row["job_id"])
    remaining = [j["job_id"] for j in protocol["jobs"] if j["job_id"] not in done]
    print(
        json.dumps(
            {
                "total_jobs": len(protocol["jobs"]),
                "completed_live": len(done),
                "remaining": len(remaining),
                "remaining_job_ids_head": remaining[:10],
                "cost_estimate": protocol["cost_estimate"],
            },
            indent=2,
        )
    )


async def _live_one(client, job, window, folder, semaphore):
    async with semaphore:
        if (folder / "response.json").exists():
            return {
                "job_id": job["job_id"],
                "status": "skipped_existing_response",
                "path": str(folder.relative_to(ROOT)).replace("\\", "/"),
            }
        req = build_ablation_request(window, job["ablation_kind"])
        write_json(folder / "request.json", req, overwrite=True)
        started = time.time()
        messages = req["messages"]
        # Prefer async path used by CP07 runner when available.
        if hasattr(client, "_chat_model") and hasattr(client, "_lc_messages"):
            reply = await client._chat_model.ainvoke(
                client._lc_messages(messages),
                **{**client._invoke_kwargs(TEMPERATURE), "max_completion_tokens": MAX_COMPLETION},
            )
            response = client._response(reply)
            content = response.content
            metadata = response.metadata
        else:
            # Sync fallback
            response = await asyncio.to_thread(
                client.chat_with_metadata, messages, temperature=TEMPERATURE
            )
            content = response.content
            metadata = getattr(response, "metadata", {})
        out = {
            "job": job,
            "ablation": req["ablation"],
            "raw_content": content,
            "metadata": metadata,
            "seconds": time.time() - started,
            "status": "returned",
            "at_UTC": datetime.now(timezone.utc).isoformat(),
        }
        write_json(folder / "response.json", out, overwrite=True)
        return {
            "job_id": job["job_id"],
            "status": "returned",
            "seconds": out["seconds"],
            "path": str(folder.relative_to(ROOT)).replace("\\", "/"),
        }


def cmd_run(max_calls: int, authorize: bool, concurrency: int):
    if not authorize:
        raise SystemExit(
            "Refusing live calls. Pass --i-authorize-live-calls after reading README.md "
            "(historical CP07 authorization is not valid for this experiment)."
        )
    if os.environ.get("ORG_ABLATION_ALLOW_LIVE") != "1":
        raise SystemExit(
            "Set ORG_ABLATION_ALLOW_LIVE=1 in the environment as a second explicit gate."
        )
    protocol = load_protocol()
    if max_calls < 1 or max_calls > protocol["max_calls"]:
        raise SystemExit(f"--max-calls must be in 1..{protocol['max_calls']}")
    from src.llm_client import OpenAICompatibleClient

    client = OpenAICompatibleClient.from_env(model=protocol.get("model") or MODEL_DEFAULT)
    if hasattr(client, "_chat_model"):
        client._chat_model.max_tokens = MAX_COMPLETION

    by_window = {w["window_id"]: w for w in protocol["windows"]}
    todo = []
    for job in protocol["jobs"]:
        folder = RUNS / "live" / job["job_id"]
        if (folder / "response.json").exists():
            continue
        todo.append(job)
        if len(todo) >= max_calls:
            break
    if not todo:
        print(json.dumps({"live": True, "started": 0, "note": "nothing remaining"}, indent=2))
        return

    async def perform():
        sem = asyncio.Semaphore(concurrency)
        results = await asyncio.gather(
            *[
                _live_one(client, job, by_window[job["window_id"]], RUNS / "live" / job["job_id"], sem)
                for job in todo
            ]
        )
        return results

    try:
        results = asyncio.run(perform())
    finally:
        if hasattr(client, "_chat_model"):
            try:
                client._chat_model.root_client.close()
            except Exception:
                pass
    ledger_path = RUNS / "live" / "ledger.json"
    prev = read_json(ledger_path) if ledger_path.exists() else {"jobs": []}
    prev_jobs = {r["job_id"]: r for r in prev.get("jobs", [])}
    for r in results:
        prev_jobs[r["job_id"]] = r
    ledger = {
        "at_UTC": datetime.now(timezone.utc).isoformat(),
        "mode": "live",
        "model": protocol.get("model"),
        "jobs": list(prev_jobs.values()),
        "authorized_max_calls_this_invocation": max_calls,
        "started_this_invocation": len(todo),
    }
    write_json(ledger_path, ledger, overwrite=True)
    write_json(EXP / "live_ledger_snapshot.json", ledger, overwrite=True)
    print(
        json.dumps(
            {
                "live": True,
                "started": len(todo),
                "returned": sum(1 for r in results if r["status"] == "returned"),
                "ledger": str(ledger_path.relative_to(ROOT)),
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(
        description="Org ablation/sensitivity experiment (final-only on frozen CP07 prompts)"
    )
    parser.add_argument(
        "command",
        choices=["prepare", "dry-run", "status", "run"],
        help="prepare|dry-run|status|run",
    )
    parser.add_argument("--overwrite-prepare", action="store_true")
    parser.add_argument("--max-calls", type=int, default=56)
    parser.add_argument("--concurrency", type=int, default=CONCURRENCY_DEFAULT)
    parser.add_argument(
        "--i-authorize-live-calls",
        action="store_true",
        help="Required explicit PIC authorization for paid/live provider calls",
    )
    args = parser.parse_args()
    if args.command == "prepare":
        cmd_prepare(overwrite=args.overwrite_prepare)
    elif args.command == "dry-run":
        cmd_dry_run()
    elif args.command == "status":
        cmd_status()
    else:
        cmd_run(args.max_calls, args.i_authorize_live_calls, args.concurrency)


if __name__ == "__main__":
    main()
