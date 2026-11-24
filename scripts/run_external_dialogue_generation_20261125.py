#!/usr/bin/env python3
"""PIC runner: generate external-arm deliberation and decision dialogues.

Commands:
  prepare   Freeze protocol, cost estimate, and input checksums (offline).
  dry-run   Materialize every request JSON under runs/… (offline).
  status    Show ledger / remaining jobs.
  run       Live model calls (dual authorize gate).
  pack      Zip live outputs for handoff when too large for git.
  reclaim   Unzip a PIC zip into the expected runs/ tree.

This is a NEW scoped live experiment. The offline external baseline
(results/experiments/external_baseline_comparison_20261123) stays frozen.
Historical authorization files are NOT a launch credential.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

EXP_ID = "external_dialogue_generation_20261125"
EXP = ROOT / "results/experiments" / EXP_ID
RUNS = ROOT / "runs" / EXP_ID
PACKAGE = ROOT / "experiment4/external_dialogue_pic_20261125"
GAME_DIR = PACKAGE / "game/case-0150_contractor_package"
AWARD_PACKET = PACKAGE / "award_packet/case-0002_contractor_package/packet.json"

MODEL_DEFAULT = "deepseek-flash"
TEMPERATURE = 0.2
ROUNDS_NUM = 12  # LLM-Deliberation convention: 4 * agents_num
WINDOW_SIZE = 6
ALLOW_ENV = "EXTERNAL_DIALOGUE_ALLOW_LIVE"

# Rough PIC planning constants (conservative).
EST_TOKENS_PER_CALL = 3500
EST_SECONDS_PER_CALL = 8.0


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj, *, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and not overwrite:
        existing = path.read_text(encoding="utf-8")
        if existing != text:
            raise ValueError(f"Refuse to overwrite changed artifact: {path}")
        return
    path.write_text(text, encoding="utf-8")


def write_text(path: Path, text: str, *, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite and path.read_text(encoding="utf-8") != text:
        raise ValueError(f"Refuse to overwrite changed artifact: {path}")
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(root: Path) -> dict[str, str]:
    rows = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rows[path.relative_to(root).as_posix()] = sha256_file(path)
    return rows


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_agents(game_dir: Path) -> list[dict]:
    agents = []
    for line in (game_dir / "config.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, file_name, role, incentive, model = [part.strip() for part in line.split(",")]
        agents.append(
            {
                "name": name,
                "file": file_name,
                "role": role,
                "incentive": incentive,
                "model": model,
            }
        )
    return agents


def load_scores(game_dir: Path, file_name: str) -> tuple[list[list[int]], int]:
    lines = [ln.strip() for ln in (game_dir / "scores_files" / f"{file_name}.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
    threshold = int(lines[-1])
    matrix = [[int(x.strip()) for x in row.split(",")] for row in lines[:-1]]
    return matrix, threshold


def issue_letters(n: int) -> list[str]:
    return [chr(ord("A") + i) for i in range(n)]


def parse_deal_codes(text: str, issues_num: int, agents_num: int) -> list[str] | None:
    """Extract codes like A1,B2 from free text / JSON."""
    if not text:
        return None
    matches = re.findall(r"\b([A-Z])(\d+)\b", text.upper())
    by_issue: dict[str, str] = {}
    for letter, option in matches:
        idx = ord(letter) - ord("A")
        opt = int(option)
        if 0 <= idx < issues_num and 1 <= opt <= agents_num:
            by_issue[letter] = f"{letter}{opt}"
    letters = issue_letters(issues_num)
    if all(letter in by_issue for letter in letters):
        return [by_issue[letter] for letter in letters]
    # also accept comma-joined exact deal
    compact = re.sub(r"\s+", "", text.upper())
    exact = re.search(r"\b((?:[A-Z]\d+)(?:,(?:[A-Z]\d+))+)\b", compact)
    if exact:
        parts = exact.group(1).split(",")
        if len(parts) == issues_num:
            return parts
    return None


def score_deal(deal: list[str], agents: list[dict], game_dir: Path) -> dict:
    utilities = {}
    thresholds = {}
    for agent in agents:
        matrix, threshold = load_scores(game_dir, agent["file"])
        thresholds[agent["name"]] = threshold
        total = 0
        for issue_i, code in enumerate(deal):
            option = int(code[1:]) - 1
            total += matrix[issue_i][option]
        utilities[agent["name"]] = total
    clears = {name: utilities[name] >= thresholds[name] for name in utilities}
    return {
        "deal": deal,
        "utility": utilities,
        "threshold": thresholds,
        "each_party_clears_threshold": clears,
        "agreement_success": bool(deal) and all(clears.values()),
    }


def build_deliberation_system(agent: dict, game_dir: Path, agents: list[dict], issues_num: int) -> str:
    global_text = (game_dir / "global_instructions.txt").read_text(encoding="utf-8")
    individual = (game_dir / "individual_instructions" / agent["incentive"] / f"{agent['file']}.txt").read_text(encoding="utf-8")
    scores, threshold = load_scores(game_dir, agent["file"])
    score_lines = ["Secret scores (do not reveal the numbers to others):"]
    for i, row in enumerate(scores):
        letter = chr(ord("A") + i)
        opts = ", ".join(f"{letter}{j+1}={v}" for j, v in enumerate(row))
        score_lines.append(f"Issue {letter}: {opts}")
    score_lines.append(f"Minimum acceptable total: {threshold}")
    p1 = next(a["name"] for a in agents if a["role"] == "p1")
    p2 = next(a["name"] for a in agents if a["role"] == "p2")
    others = ", ".join(a["name"] for a in agents)
    example_deal = ",".join(f"{chr(ord('A') + i)}1" for i in range(issues_num))
    voting = (
        f"There are {len(agents)} parties: {others}. "
        f'"{p1}" is p1 (can propose the final deal). "{p2}" is p2. '
        f"A complete deal names one option per issue, written as codes like {example_deal}. "
        "Cooperative rule: any deal at or above your minimum is better than no deal."
    )
    output = (
        "Respond ONLY as a JSON object with keys: "
        "scratchpad (private chain-of-thought), "
        "public_answer (what other parties hear; no secret scores), "
        "proposed_deal (comma-separated option codes covering every issue, or null if not proposing yet)."
    )
    return "\n\n".join([global_text.strip(), individual.strip(), "\n".join(score_lines), voting, output])


def build_history_prompt(agent_name: str, public_history: list[dict], window: int) -> str:
    recent = public_history[-window:]
    if not recent:
        return "No prior public statements yet."
    lines = []
    for turn in recent:
        speaker = "You" if turn["agent"] == agent_name else turn["agent"]
        lines.append(f"{speaker}: {turn['public_answer']}")
    return "Public negotiation history (most recent last):\n" + "\n".join(lines)


def job_specs(protocol: dict) -> list[dict]:
    jobs = []
    for arm in protocol["arms"]:
        for job in arm["jobs"]:
            jobs.append({**job, "arm": arm["id"]})
    return jobs


def protocol_path() -> Path:
    return EXP / "protocol.json"


def load_protocol() -> dict:
    path = protocol_path()
    if not path.exists():
        raise SystemExit("protocol.json missing; run prepare first")
    return read_json(path)


def cmd_prepare(args: argparse.Namespace) -> None:
    EXP.mkdir(parents=True, exist_ok=True)
    if not GAME_DIR.is_dir():
        raise SystemExit(f"Missing game bundle: {GAME_DIR}")
    if not AWARD_PACKET.is_file():
        raise SystemExit(f"Missing award packet: {AWARD_PACKET}")

    agents = load_agents(GAME_DIR)
    issues_num = len(load_scores(GAME_DIR, agents[0]["file"])[0])
    award = read_json(AWARD_PACKET)
    model = args.model or MODEL_DEFAULT

    # Rewrite executable config copy under package (do not alter offline baseline result tree).
    live_config = "\n".join(
        f"{a['name']},{a['file']},{a['role']},{a['incentive']},{model}" for a in agents
    ) + "\n"
    write_text(GAME_DIR / "config.live.txt", live_config, overwrite=True)

    initial_deal = (GAME_DIR / "initial_deal.txt").read_text(encoding="utf-8").strip()

    delib_jobs = []
    # Round-robin speaking turns, then p1 final deal suggestion.
    order = agents  # config order
    for round_i in range(ROUNDS_NUM):
        agent = order[round_i % len(order)]
        delib_jobs.append(
            {
                "job_id": f"llm_deliberation-round-{round_i+1:02d}-{agent['name']}",
                "kind": "negotiation_turn",
                "round": round_i + 1,
                "agent": agent["name"],
                "final": False,
            }
        )
    p1 = next(a for a in agents if a["role"] == "p1")
    delib_jobs.append(
        {
            "job_id": f"llm_deliberation-final-{p1['name']}",
            "kind": "final_deal",
            "round": ROUNDS_NUM + 1,
            "agent": p1["name"],
            "final": True,
        }
    )

    capstone_jobs = []
    for turn in (1, 2):
        for agent in agents:
            capstone_jobs.append(
                {
                    "job_id": f"capstone_consortium-turn{turn}-{agent['name']}",
                    "kind": "capstone_negotiation_turn",
                    "turn": turn,
                    "agent": agent["name"],
                }
            )
    lead = next(a for a in agents if a["role"] == "p1")
    capstone_jobs.append(
        {
            "job_id": f"capstone_consortium-decision-{lead['name']}",
            "kind": "capstone_consortium_decision",
            "agent": lead["name"],
        }
    )

    owner_roles = award["owner_roster"]
    # Keep decision dialogue small: first three roster members (or all if fewer).
    discussants = owner_roles[:3]
    award_jobs = []
    for stage_i, stage in enumerate(("award_risk_review", "final_award_alignment"), start=1):
        for member in discussants:
            mid = member.get("agent_id") or member.get("member_id") or member.get("name") or f"member-{stage_i}"
            award_jobs.append(
                {
                    "job_id": f"capstone_award-{stage}-{mid}",
                    "kind": "award_discussion",
                    "stage": stage,
                    "member_id": mid,
                }
            )
    award_jobs.append(
        {
            "job_id": "capstone_award-final-decision",
            "kind": "award_decision",
            "stage": "final",
            "member_id": award["owner"]["company_id"],
        }
    )

    arms = [
        {
            "id": "llm_deliberation",
            "title": "External LLM-Deliberation consortium dialogue",
            "baseline": "S-Abdelnabi/LLM-Deliberation cooperative game on frozen case-0150 contractor package",
            "jobs": delib_jobs,
            "calls": len(delib_jobs),
        },
        {
            "id": "capstone_consortium_decision",
            "title": "Capstone paired consortium deliberation + decision",
            "baseline": "Same firms/issues as the external game; Capstone external-negotiation style",
            "jobs": capstone_jobs,
            "calls": len(capstone_jobs),
        },
        {
            "id": "capstone_award_decision",
            "title": "Capstone owner award decision dialogue",
            "baseline": "Frozen case-0002 contractor_package bids vs silent pymcdm TOPSIS ranking",
            "jobs": award_jobs,
            "calls": len(award_jobs),
        },
    ]
    total_calls = sum(arm["calls"] for arm in arms)
    protocol = {
        "experiment_id": EXP_ID,
        "created_at": utc_now(),
        "model": model,
        "temperature": TEMPERATURE,
        "allow_env": ALLOW_ENV,
        "game": {
            "path": str(GAME_DIR.relative_to(ROOT)),
            "case_id": "case-0150",
            "package_id": "contractor_package",
            "agents": agents,
            "issues_num": issues_num,
            "agents_num": len(agents),
            "rounds_num": ROUNDS_NUM,
            "window_size": WINDOW_SIZE,
            "initial_deal": initial_deal,
            "sha256": sha256_tree(GAME_DIR),
        },
        "award_packet": {
            "path": str(AWARD_PACKET.relative_to(ROOT)),
            "case_id": award["case_id"],
            "package_id": award["package_id"],
            "sha256": sha256_file(AWARD_PACKET),
            "discussant_count": len(discussants),
        },
        "arms": arms,
        "planned_calls": total_calls,
        "notes": [
            "Does not auto-start. Dual gate required for live calls.",
            "Does not modify frozen offline baseline scores under external_baseline_comparison_20261123.",
            "Outputs go under runs/external_dialogue_generation_20261125/ (gitignored).",
        ],
    }
    cost = {
        "planned_calls": total_calls,
        "model": model,
        "assumed_tokens_per_call": EST_TOKENS_PER_CALL,
        "expected_tokens": total_calls * EST_TOKENS_PER_CALL,
        "assumed_seconds_per_call": EST_SECONDS_PER_CALL,
        "ideal_wall_clock_minutes_serial": round(total_calls * EST_SECONDS_PER_CALL / 60, 1),
        "by_arm": {arm["id"]: arm["calls"] for arm in arms},
        "money_note": "Quote from the current provider dashboard; repo does not pin a unit price.",
    }
    manifest = {
        "experiment_id": EXP_ID,
        "package": str(PACKAGE.relative_to(ROOT)),
        "game_files": len(protocol["game"]["sha256"]),
        "award_packet_sha256": protocol["award_packet"]["sha256"],
        "planned_calls": total_calls,
    }
    write_json(EXP / "protocol.json", protocol, overwrite=True)
    write_json(EXP / "cost_estimate.json", cost, overwrite=True)
    write_json(EXP / "sample_manifest.json", manifest, overwrite=True)
    write_json(
        EXP / "index.json",
        {
            "experiment_id": EXP_ID,
            "status": "prepared",
            "commands": {
                "prepare": "python3 scripts/run_external_dialogue_generation_20261125.py prepare",
                "dry_run": "python3 scripts/run_external_dialogue_generation_20261125.py dry-run",
                "status": "python3 scripts/run_external_dialogue_generation_20261125.py status",
                "run": f"{ALLOW_ENV}=1 python3 scripts/run_external_dialogue_generation_20261125.py run --i-authorize-live-calls",
                "one_command": f"{ALLOW_ENV}=1 bash scripts/external_dialogue_generation.sh all",
                "pack": "python3 scripts/run_external_dialogue_generation_20261125.py pack",
                "reclaim": "python3 scripts/run_external_dialogue_generation_20261125.py reclaim --zip <zip>",
            },
            "pic_guide": str((PACKAGE / "README.md").relative_to(ROOT)),
            "offline_baseline": "results/experiments/external_baseline_comparison_20261123/SUMMARY.md",
        },
        overwrite=True,
    )
    print(json.dumps({"prepared": True, "planned_calls": total_calls, "protocol": str(protocol_path())}, ensure_ascii=False))


def materialize_requests(protocol: dict) -> list[dict]:
    agents = {a["name"]: a for a in protocol["game"]["agents"]}
    game_dir = ROOT / protocol["game"]["path"]
    issues_num = protocol["game"]["issues_num"]
    award = read_json(ROOT / protocol["award_packet"]["path"])
    ledger = []
    public_seed = [
        {
            "agent": "system",
            "public_answer": f"Opening deal suggested by p1 preference seed: {protocol['game']['initial_deal']}",
        }
    ]

    # Arm 1 prompts depend on prior public answers at live time; dry-run stores templates.
    for job in next(a for a in protocol["arms"] if a["id"] == "llm_deliberation")["jobs"]:
        agent = agents[job["agent"]]
        system = build_deliberation_system(agent, game_dir, protocol["game"]["agents"], issues_num)
        if job["kind"] == "final_deal":
            user = (
                "This is the final round. Propose one complete deal as option codes covering every issue. "
                "public_answer must state the deal clearly. proposed_deal must be the comma-separated codes.\n"
                "HISTORY_PLACEHOLDER"
            )
        else:
            user = (
                f"Round {job['round']} of {protocol['game']['rounds_num']}. "
                "Make one public statement. If you propose a deal, set proposed_deal; otherwise null.\n"
                "HISTORY_PLACEHOLDER"
            )
        req = {
            "job_id": job["job_id"],
            "arm": "llm_deliberation",
            "kind": job["kind"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "history_seed": public_seed,
            "meta": job,
        }
        path = RUNS / "dry" / "llm_deliberation" / job["job_id"] / "request.json"
        write_json(path, req, overwrite=True)
        ledger.append({"job_id": job["job_id"], "arm": "llm_deliberation", "request": str(path.relative_to(ROOT))})

    for job in next(a for a in protocol["arms"] if a["id"] == "capstone_consortium_decision")["jobs"]:
        agent = agents[job["agent"]]
        company_blob = (game_dir / "individual_instructions" / agent["incentive"] / f"{agent['file']}.txt").read_text(encoding="utf-8")
        global_text = (game_dir / "global_instructions.txt").read_text(encoding="utf-8")
        if job["kind"] == "capstone_consortium_decision":
            system = (
                "You are the lead firm finalizing a consortium role split after negotiation. "
                "Return JSON with keys: thoughts, content, role_split (object mapping firm id to responsibility text), "
                "status (formed|not_formed), agreement_summary."
            )
            user = (
                f"Game:\n{global_text}\n\nYour firm brief:\n{company_blob}\n\n"
                "Using the negotiation so far (HISTORY_PLACEHOLDER), output the final role split. "
                "Each included capability must be assigned to one firm."
            )
        else:
            system = (
                "You are negotiating a construction consortium role split with other firms. "
                "Return JSON with keys: thoughts, content, recommendation, decision_impact, "
                "verification_requests (list), proposed_deal (codes or null). "
                "content is what counterparts hear; do not reveal secret numeric scores."
            )
            user = (
                f"Turn {job['turn']}. Game:\n{global_text}\n\nYour firm brief:\n{company_blob}\n\n"
                "HISTORY_PLACEHOLDER\n"
                "Speak for your firm only. Propose or react to a capability assignment."
            )
        req = {
            "job_id": job["job_id"],
            "arm": "capstone_consortium_decision",
            "kind": job["kind"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "meta": job,
        }
        path = RUNS / "dry" / "capstone_consortium_decision" / job["job_id"] / "request.json"
        write_json(path, req, overwrite=True)
        ledger.append({"job_id": job["job_id"], "arm": "capstone_consortium_decision", "request": str(path.relative_to(ROOT))})

    discussants = award["owner_roster"][: protocol["award_packet"]["discussant_count"]]
    topsis = award["topsis_baseline"]
    bid_lines = []
    for bid in award["bids"]:
        bid_lines.append(
            f"- {bid.get('bidder_id')} / {bid.get('bidder_name')}: price={bid.get('quotation')}, "
            f"summary={str(bid.get('submission_summary') or '')[:180]}"
        )
    eval_text = json.dumps(
        {
            "recommended_winner": award["evaluation_report"].get("recommended_winner"),
            "comparison_summary": award["evaluation_report"].get("comparison_summary"),
            "owner_review_notes": award["evaluation_report"].get("owner_review_notes"),
        },
        ensure_ascii=False,
        indent=2,
    )
    topsis_text = json.dumps(
        {
            "applied_criteria": topsis.get("applied_criteria"),
            "topsis_ranking_high_to_low": topsis.get("topsis_ranking_high_to_low"),
            "award_winner_historical": topsis.get("award_winner"),
            "winner_in_top_group": topsis.get("winner_in_top_group"),
        },
        ensure_ascii=False,
        indent=2,
    )
    for job in next(a for a in protocol["arms"] if a["id"] == "capstone_award_decision")["jobs"]:
        if job["kind"] == "award_discussion":
            member = next(
                (
                    m
                    for m in discussants
                    if (m.get("agent_id") or m.get("member_id") or m.get("name")) == job["member_id"]
                ),
                {"role": job["member_id"], "responsibilities": ""},
            )
            system = (
                f"You are owner-side staff ({job['member_id']}) in stage {job['stage']}. "
                "Return JSON with keys: thoughts, content, recommendation, risks. "
                "Discuss which eligible bidder should receive the award. Do not invent bids."
            )
            user = (
                f"Owner: {award['owner']['company_name']}\n"
                f"Package: {award['package_id']}\n"
                f"Your role card: {json.dumps(member, ensure_ascii=False)}\n"
                f"Eligible bids:\n" + "\n".join(bid_lines) + "\n\n"
                f"Evaluation report excerpt:\n{eval_text}\n\n"
                f"Silent pymcdm TOPSIS baseline (numeric only; not binding):\n{topsis_text}\n\n"
                "HISTORY_PLACEHOLDER"
            )
        else:
            system = (
                "You are the owner making the final award decision after internal discussion. "
                "Return JSON with keys: thoughts, selected_bidder_id (or null), award_reason, "
                "rejected_bidders (list of {bidder_id, reason}), conditions_pending (list)."
            )
            user = (
                f"Package: {award['package_id']}\nEligible bids:\n" + "\n".join(bid_lines) + "\n\n"
                f"Evaluation report excerpt:\n{eval_text}\n\n"
                f"Silent TOPSIS baseline:\n{topsis_text}\n\n"
                "Owner discussion so far:\nHISTORY_PLACEHOLDER\n"
                "Choose one selected_bidder_id from the eligible bids, or null if no award."
            )
        req = {
            "job_id": job["job_id"],
            "arm": "capstone_award_decision",
            "kind": job["kind"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "meta": job,
        }
        path = RUNS / "dry" / "capstone_award_decision" / job["job_id"] / "request.json"
        write_json(path, req, overwrite=True)
        ledger.append({"job_id": job["job_id"], "arm": "capstone_award_decision", "request": str(path.relative_to(ROOT))})

    write_json(RUNS / "dry_run_ledger.json", {"created_at": utc_now(), "jobs": ledger}, overwrite=True)
    write_json(EXP / "dry_run_ledger.json", {"created_at": utc_now(), "jobs": ledger, "note": "paths under runs/ are gitignored live work"}, overwrite=True)
    return ledger


def cmd_dry_run(_args: argparse.Namespace) -> None:
    protocol = load_protocol()
    ledger = materialize_requests(protocol)
    print(json.dumps({"dry_run": True, "jobs": len(ledger), "ledger": str((RUNS / "dry_run_ledger.json"))}, ensure_ascii=False))


def _response_path(arm: str, job_id: str) -> Path:
    return RUNS / "live" / arm / job_id / "response.json"


def _request_live_path(arm: str, job_id: str) -> Path:
    return RUNS / "live" / arm / job_id / "request.json"


def status_payload() -> dict:
    protocol = load_protocol()
    jobs = job_specs(protocol)
    done = []
    pending = []
    for job in jobs:
        path = _response_path(job["arm"], job["job_id"])
        if path.exists():
            done.append(job["job_id"])
        else:
            pending.append(job["job_id"])
    return {
        "experiment_id": EXP_ID,
        "planned": len(jobs),
        "done": len(done),
        "pending": len(pending),
        "pending_job_ids": pending[:20],
        "live_root": str(RUNS / "live"),
    }


def cmd_status(_args: argparse.Namespace) -> None:
    print(json.dumps(status_payload(), ensure_ascii=False, indent=2))


async def _achat(client, messages: list[dict], temperature: float) -> dict:
    from src.llm_client import extract_json_object

    response = await client.achat_with_metadata(messages, temperature=temperature)
    parsed = extract_json_object(response.content)
    return {
        "content": response.content,
        "parsed": parsed,
        "metadata": response.metadata,
        "created_at": utc_now(),
    }


def _fill_history(messages: list[dict], history_text: str) -> list[dict]:
    filled = []
    for message in messages:
        content = message["content"].replace("HISTORY_PLACEHOLDER", history_text)
        filled.append({"role": message["role"], "content": content})
    return filled


async def run_llm_deliberation(protocol: dict, client, max_calls: int, calls_used: list[int]) -> dict:
    arm = "llm_deliberation"
    game_dir = ROOT / protocol["game"]["path"]
    agents = {a["name"]: a for a in protocol["game"]["agents"]}
    issues_num = protocol["game"]["issues_num"]
    agents_num = protocol["game"]["agents_num"]
    public_history = [
        {
            "agent": "system",
            "public_answer": f"Opening deal suggested by p1 preference seed: {protocol['game']['initial_deal']}",
        }
    ]
    rounds_out = []
    final_deal = None
    for job in next(a for a in protocol["arms"] if a["id"] == arm)["jobs"]:
        if calls_used[0] >= max_calls:
            break
        resp_path = _response_path(arm, job["job_id"])
        if resp_path.exists():
            existing = read_json(resp_path)
            public_history.append(
                {
                    "agent": job["agent"],
                    "public_answer": existing.get("parsed", {}).get("public_answer") or existing.get("content", ""),
                }
            )
            if job.get("final"):
                final_deal = parse_deal_codes(
                    str(existing.get("parsed", {}).get("proposed_deal") or existing.get("parsed", {}).get("public_answer") or ""),
                    issues_num,
                    agents_num,
                )
            rounds_out.append({"job_id": job["job_id"], "skipped_existing": True})
            continue
        dry = read_json(RUNS / "dry" / arm / job["job_id"] / "request.json")
        history_text = build_history_prompt(job["agent"], public_history, protocol["game"]["window_size"])
        messages = _fill_history(dry["messages"], history_text)
        write_json(_request_live_path(arm, job["job_id"]), {"messages": messages, "meta": job}, overwrite=True)
        result = await _achat(client, messages, protocol["temperature"])
        write_json(resp_path, result, overwrite=True)
        calls_used[0] += 1
        public = result["parsed"].get("public_answer") or ""
        public_history.append({"agent": job["agent"], "public_answer": public})
        if job.get("final") or result["parsed"].get("proposed_deal"):
            candidate = parse_deal_codes(
                str(result["parsed"].get("proposed_deal") or public),
                issues_num,
                agents_num,
            )
            if candidate:
                final_deal = candidate
        rounds_out.append({"job_id": job["job_id"], "agent": job["agent"], "public_answer": public})

    scored = None if not final_deal else score_deal(final_deal, protocol["game"]["agents"], game_dir)
    summary = {
        "arm": arm,
        "dialogue_run": True,
        "model_calls": calls_used[0],
        "rounds": rounds_out,
        "final_deal": final_deal,
        "score": scored,
        "public_history": public_history,
    }
    write_json(RUNS / "live" / arm / "summary.json", summary, overwrite=True)
    return summary


async def run_capstone_consortium(protocol: dict, client, max_calls: int, calls_used: list[int]) -> dict:
    arm = "capstone_consortium_decision"
    game_dir = ROOT / protocol["game"]["path"]
    issues_num = protocol["game"]["issues_num"]
    agents_num = protocol["game"]["agents_num"]
    public_history: list[dict] = []
    decision = None
    for job in next(a for a in protocol["arms"] if a["id"] == arm)["jobs"]:
        if calls_used[0] >= max_calls:
            break
        resp_path = _response_path(arm, job["job_id"])
        if resp_path.exists():
            existing = read_json(resp_path)
            public_history.append(
                {
                    "agent": job["agent"],
                    "public_answer": existing.get("parsed", {}).get("content")
                    or existing.get("parsed", {}).get("public_answer")
                    or "",
                }
            )
            if job["kind"] == "capstone_consortium_decision":
                decision = existing.get("parsed")
            continue
        dry = read_json(RUNS / "dry" / arm / job["job_id"] / "request.json")
        history_text = build_history_prompt(job["agent"], public_history, WINDOW_SIZE)
        messages = _fill_history(dry["messages"], history_text)
        write_json(_request_live_path(arm, job["job_id"]), {"messages": messages, "meta": job}, overwrite=True)
        result = await _achat(client, messages, protocol["temperature"])
        write_json(resp_path, result, overwrite=True)
        calls_used[0] += 1
        public = result["parsed"].get("content") or result["parsed"].get("public_answer") or ""
        public_history.append({"agent": job["agent"], "public_answer": public})
        if job["kind"] == "capstone_consortium_decision":
            decision = result["parsed"]

    deal = None
    if decision:
        deal = parse_deal_codes(json.dumps(decision, ensure_ascii=False), issues_num, agents_num)
        if not deal:
            # derive from role_split stems if codes absent
            role_split = decision.get("role_split") or {}
            issues = []
            global_text = (game_dir / "global_instructions.txt").read_text(encoding="utf-8")
            for match in re.finditer(r'Issue ([A-Z]): "([^"]+)"', global_text):
                issues.append((match.group(1), match.group(2)))
            agents = [a["name"] for a in protocol["game"]["agents"]]
            codes = []
            for letter, requirement in issues:
                hits = []
                for name in agents:
                    text = str(role_split.get(name) or "")
                    stem = requirement.replace("能力", "")
                    if stem and stem in text:
                        hits.append(name)
                if len(hits) == 1:
                    codes.append(f"{letter}{agents.index(hits[0]) + 1}")
            if len(codes) == issues_num:
                deal = codes
    scored = None if not deal else score_deal(deal, protocol["game"]["agents"], game_dir)
    summary = {
        "arm": arm,
        "dialogue_run": True,
        "decision": decision,
        "final_deal": deal,
        "score": scored,
        "public_history": public_history,
    }
    write_json(RUNS / "live" / arm / "summary.json", summary, overwrite=True)
    return summary


async def run_capstone_award(protocol: dict, client, max_calls: int, calls_used: list[int]) -> dict:
    arm = "capstone_award_decision"
    award = read_json(ROOT / protocol["award_packet"]["path"])
    public_history: list[dict] = []
    decision = None
    for job in next(a for a in protocol["arms"] if a["id"] == arm)["jobs"]:
        if calls_used[0] >= max_calls:
            break
        resp_path = _response_path(arm, job["job_id"])
        if resp_path.exists():
            existing = read_json(resp_path)
            public_history.append(
                {
                    "agent": job.get("member_id") or "owner",
                    "public_answer": existing.get("parsed", {}).get("content")
                    or existing.get("parsed", {}).get("award_reason")
                    or "",
                }
            )
            if job["kind"] == "award_decision":
                decision = existing.get("parsed")
            continue
        dry = read_json(RUNS / "dry" / arm / job["job_id"] / "request.json")
        history_text = build_history_prompt(job.get("member_id") or "owner", public_history, WINDOW_SIZE)
        messages = _fill_history(dry["messages"], history_text)
        write_json(_request_live_path(arm, job["job_id"]), {"messages": messages, "meta": job}, overwrite=True)
        result = await _achat(client, messages, protocol["temperature"])
        write_json(resp_path, result, overwrite=True)
        calls_used[0] += 1
        public = (
            result["parsed"].get("content")
            or result["parsed"].get("award_reason")
            or result["parsed"].get("recommendation")
            or ""
        )
        public_history.append({"agent": job.get("member_id") or "owner", "public_answer": public})
        if job["kind"] == "award_decision":
            decision = result["parsed"]

    selected = None if not decision else decision.get("selected_bidder_id")
    topsis_top = award["topsis_baseline"]["topsis_ranking_high_to_low"][0][0]
    historical = award["topsis_baseline"]["award_winner"]
    summary = {
        "arm": arm,
        "dialogue_run": True,
        "decision": decision,
        "selected_bidder_id": selected,
        "matches_topsis_top": selected == topsis_top,
        "matches_historical_award": selected == historical,
        "topsis_top": topsis_top,
        "historical_award": historical,
        "public_history": public_history,
    }
    write_json(RUNS / "live" / arm / "summary.json", summary, overwrite=True)
    return summary


async def cmd_run_async(args: argparse.Namespace) -> None:
    if not args.i_authorize_live_calls:
        raise SystemExit("Refusing live calls: pass --i-authorize-live-calls")
    if os.getenv(ALLOW_ENV, "").strip() != "1":
        raise SystemExit(f"Refusing live calls: set {ALLOW_ENV}=1")
    from src.llm_client import OpenAICompatibleClient

    protocol = load_protocol()
    if not (RUNS / "dry_run_ledger.json").exists():
        materialize_requests(protocol)
    client = OpenAICompatibleClient.from_env(model=protocol["model"])
    max_calls = args.max_calls if args.max_calls is not None else protocol["planned_calls"]
    calls_used = [0]
    started = time.time()
    summaries = {}
    # Sequential arms keep history coherent and stay within PIC cost control.
    summaries["llm_deliberation"] = await run_llm_deliberation(protocol, client, max_calls, calls_used)
    if calls_used[0] < max_calls:
        summaries["capstone_consortium_decision"] = await run_capstone_consortium(protocol, client, max_calls, calls_used)
    if calls_used[0] < max_calls:
        summaries["capstone_award_decision"] = await run_capstone_award(protocol, client, max_calls, calls_used)
    report = {
        "experiment_id": EXP_ID,
        "finished_at": utc_now(),
        "elapsed_seconds": round(time.time() - started, 1),
        "model_calls": calls_used[0],
        "max_calls": max_calls,
        "status": status_payload(),
        "summaries": {
            key: {
                "final_deal": value.get("final_deal"),
                "agreement_success": (value.get("score") or {}).get("agreement_success"),
                "selected_bidder_id": value.get("selected_bidder_id"),
                "matches_topsis_top": value.get("matches_topsis_top"),
                "matches_historical_award": value.get("matches_historical_award"),
            }
            for key, value in summaries.items()
        },
    }
    write_json(RUNS / "live" / "REPORT.json", report, overwrite=True)
    write_json(EXP / "live_report_pointer.json", {"report": str((RUNS / "live" / "REPORT.json").relative_to(ROOT)), "model_calls": calls_used[0]}, overwrite=True)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def cmd_run(args: argparse.Namespace) -> None:
    asyncio.run(cmd_run_async(args))


def cmd_pack(args: argparse.Namespace) -> None:
    live = RUNS / "live"
    if not live.exists():
        raise SystemExit(f"No live outputs at {live}")
    out_dir = Path(args.out) if args.out else ROOT / "21 nov updates"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zip_path = out_dir / f"{EXP_ID}_{stamp}.zip"
    files = sorted(p for p in live.rglob("*") if p.is_file())
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in files:
            bundle.write(path, Path(EXP_ID).joinpath(path.relative_to(RUNS)).as_posix())
        # Include small experiment index for reclaimers.
        for name in ("protocol.json", "cost_estimate.json", "sample_manifest.json", "index.json"):
            src = EXP / name
            if src.exists():
                bundle.write(src, Path(EXP_ID).joinpath("experiment_meta", name).as_posix())
    print(
        json.dumps(
            {
                "zip": str(zip_path),
                "bytes": zip_path.stat().st_size,
                "files": len(files),
                "unzip_to": str(RUNS),
                "reclaim_command": f"python3 scripts/run_external_dialogue_generation_20261125.py reclaim --zip '{zip_path}'",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def cmd_reclaim(args: argparse.Namespace) -> None:
    zip_path = Path(args.zip)
    if not zip_path.is_file():
        raise SystemExit(f"Zip not found: {zip_path}")
    target = RUNS
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as bundle:
        for info in bundle.infolist():
            name = info.filename
            if name.endswith("/"):
                continue
            # Expected: external_dialogue_generation_20261125/live/...
            parts = Path(name).parts
            if not parts or parts[0] != EXP_ID:
                raise SystemExit(f"Unexpected zip member (refuse unsafe extract): {name}")
            rel = Path(*parts[1:])
            if rel.parts and rel.parts[0] == "experiment_meta":
                dest = EXP / rel.parts[-1]
            else:
                dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)
    print(json.dumps({"reclaimed_to": str(target), "meta": str(EXP), "status": status_payload()}, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_prep = sub.add_parser("prepare", help="Freeze protocol and cost estimate")
    p_prep.add_argument("--model", default=MODEL_DEFAULT)
    p_prep.set_defaults(func=cmd_prepare)

    p_dry = sub.add_parser("dry-run", help="Materialize request JSONs offline")
    p_dry.set_defaults(func=cmd_dry_run)

    p_status = sub.add_parser("status", help="Show progress")
    p_status.set_defaults(func=cmd_status)

    p_run = sub.add_parser("run", help="Live model calls")
    p_run.add_argument("--i-authorize-live-calls", action="store_true")
    p_run.add_argument("--max-calls", type=int, default=None)
    p_run.set_defaults(func=cmd_run)

    p_pack = sub.add_parser("pack", help="Zip live outputs for handoff")
    p_pack.add_argument("--out", default="", help="Directory for the zip (default: 21 nov updates/)")
    p_pack.set_defaults(func=cmd_pack)

    p_reclaim = sub.add_parser("reclaim", help="Unzip PIC zip into runs/")
    p_reclaim.add_argument("--zip", required=True)
    p_reclaim.set_defaults(func=cmd_reclaim)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
