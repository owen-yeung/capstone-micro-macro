#!/usr/bin/env python3
"""Provider-compare harness: DeepSeek baseline vs Qwen3.5-Flash (DashScope).

Default is dry-run (writes a plan/manifest only). Pass --execute to launch real
model batches. Requires the matching API keys in the environment / .env.

Protocol (interim §6.2):
  - same frozen 28 cases, ablation=none, temperature 0.2
  - providers: deepseek (reference) and qwen/qwen3.5-flash (second provider)
  - seeds: 3 by default (use --seeds 5 for the upper protocol bound)
  - score each completed seed with size-matched hit@1; do not merge providers
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_providers import load_project_env, resolve_provider_config  # noqa: E402
from src.tender_metrics.size_matched_baseline import (  # noqa: E402
    aggregate_package_scores,
    score_archived_28_cases,
)

DEFAULT_CONFIG = ROOT / "validation/benchmark_ge3_compact/config_final28.json"
DEFAULT_BENCH = ROOT / "validation/benchmark_ge3_compact/data/hidden_benchmark_project_enterprises.csv"
DEFAULT_OUTPUT = ROOT / "runs/provider_compare_qwen_20261117"
TRACKED = ROOT / "results/experiments/provider_compare_qwen_20261117"

DEFAULT_ARMS = (
    {"provider": "deepseek", "model": "deepseek-chat", "role": "reference"},
    {"provider": "qwen", "model": "qwen3.5-flash", "role": "second_provider"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seeds", type=int, default=3, choices=[1, 2, 3, 4, 5])
    parser.add_argument("--profile", choices=["full", "smoke"], default="full")
    parser.add_argument("--max-cases", type=int, default=0, help="Optional cap for smoke/debug.")
    parser.add_argument(
        "--providers",
        default="deepseek,qwen",
        help="Comma-separated providers to include (subset of deepseek,qwen,openai,groq).",
    )
    parser.add_argument(
        "--qwen-model",
        default="qwen3.5-flash",
        help="Qwen model id on DashScope. Default: qwen3.5-flash.",
    )
    parser.add_argument(
        "--deepseek-model",
        default="",
        help="Optional DeepSeek model override (default DEEPSEEK_MODEL / deepseek-chat).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually launch main.py batches. Without this flag only the plan is written.",
    )
    parser.add_argument(
        "--score-only",
        action="store_true",
        help="Skip launching runs; score any completed seed directories already under --output-root.",
    )
    parser.add_argument(
        "--local-test-client",
        action="store_true",
        help="Use MockLLMClient for wiring tests (no paid calls).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_project_env()
    arms = _selected_arms(args)
    args.output_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "experiment_id": "provider_compare_qwen_20261117",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "protocol": {
            "cases": "frozen interim 28 via config_final28.json",
            "ablation": "none",
            "temperature": 0.2,
            "seeds": args.seeds,
            "profile": args.profile,
            "reporting": "size-matched hit@1 per provider/seed; never merge providers",
            "qwen_thinking": "disabled via enable_thinking=false",
        },
        "arms": arms,
        "execute": bool(args.execute),
        "score_only": bool(args.score_only),
        "status": "planned",
        "runs": [],
        "notes": [
            "Qwen3.5-Flash is the second provider (DashScope OpenAI-compatible).",
            "DeepSeek remains the reference arm.",
            "Dry-run is the default. --execute requires API keys and authorized spend.",
        ],
    }

    if args.score_only:
        scores = _score_completed(args.output_root)
        manifest["status"] = "scored_existing"
        manifest["scores"] = scores
        _write_manifest(args.output_root, manifest)
        print(json.dumps({"status": manifest["status"], "scored_runs": len(scores)}, indent=2))
        return 0

    planned = []
    for arm in arms:
        for seed in range(1, args.seeds + 1):
            run_dir = args.output_root / f"{arm['provider']}__{arm['model'].replace('/', '_')}__seed{seed}"
            planned.append(
                {
                    "provider": arm["provider"],
                    "model": arm["model"],
                    "role": arm["role"],
                    "seed": seed,
                    "run_dir": str(run_dir),
                    "command": _command(args, arm, run_dir),
                }
            )
    manifest["runs"] = planned
    _write_manifest(args.output_root, manifest)
    _write_plan(args.output_root, planned, execute=args.execute)
    _mirror_docs(args.output_root)

    if not args.execute:
        print(f"Dry-run plan written to {args.output_root / 'PLAN.md'}")
        print("Re-run with --execute after API keys and spend authorization are in place.")
        return 0

    if not args.local_test_client:
        _preflight_keys(arms)
    failures = []
    for item in planned:
        run_dir = Path(item["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["LLM_PROVIDER"] = item["provider"]
        if item["provider"] == "qwen":
            env["QWEN_MODEL"] = item["model"]
        elif item["provider"] == "deepseek":
            env["DEEPSEEK_MODEL"] = item["model"]
        elif item["provider"] == "openai":
            env["OPENAI_MODEL"] = item["model"]
        elif item["provider"] == "groq":
            env["GROQ_MODEL"] = item["model"]
        if args.local_test_client:
            env["CODEDEMO_USE_LOCAL_TEST_CLIENT"] = "1"
        env.setdefault("CODEDEMO_LLM_CONCURRENCY", "3")
        print(f"Launching {item['provider']} seed={item['seed']} -> {run_dir}")
        completed = subprocess.run(item["command"], cwd=ROOT, env=env, check=False)
        item["exit_code"] = completed.returncode
        if completed.returncode != 0:
            failures.append(item)
    scores = _score_completed(args.output_root)
    manifest["status"] = "completed_with_failures" if failures else "completed"
    manifest["failures"] = failures
    manifest["scores"] = scores
    _write_manifest(args.output_root, manifest)
    _write_score_report(args.output_root, scores)
    _mirror_docs(args.output_root)
    print(json.dumps({"status": manifest["status"], "failures": len(failures), "scored_runs": len(scores)}, indent=2))
    return 1 if failures else 0


def _selected_arms(args: argparse.Namespace) -> list[dict]:
    wanted = {part.strip().lower() for part in args.providers.split(",") if part.strip()}
    arms = []
    for arm in DEFAULT_ARMS:
        if arm["provider"] not in wanted:
            continue
        item = dict(arm)
        if item["provider"] == "qwen":
            item["model"] = args.qwen_model
        elif item["provider"] == "deepseek" and args.deepseek_model:
            item["model"] = args.deepseek_model
        arms.append(item)
    if "openai" in wanted:
        arms.append({"provider": "openai", "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"), "role": "optional_third"})
    if "groq" in wanted:
        arms.append(
            {
                "provider": "groq",
                "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
                "role": "optional_alternate",
            }
        )
    if not arms:
        raise ValueError("No providers selected")
    return arms


def _command(args: argparse.Namespace, arm: dict, run_dir: Path) -> list[str]:
    command = [
        sys.executable,
        str(ROOT / "main.py"),
        "--mode",
        "case",
        "--run-scope",
        "batch",
        "--config",
        str(args.config),
        "--profile",
        args.profile,
        "--ablation",
        "none",
        "--llm-provider",
        arm["provider"],
        "--llm-model",
        arm["model"],
        "--output-dir",
        str(run_dir),
    ]
    if args.max_cases:
        command.extend(["--max-cases", str(args.max_cases)])
    return command


def _preflight_keys(arms: list[dict]) -> None:
    for arm in arms:
        resolve_provider_config(arm["provider"], model=arm["model"])


def _score_completed(output_root: Path) -> list[dict]:
    scores = []
    if not output_root.exists():
        return scores
    for run_dir in sorted(path for path in output_root.iterdir() if path.is_dir()):
        cases_root = _find_cases_root(run_dir)
        if cases_root is None:
            continue
        try:
            packages = score_archived_28_cases(cases_root, DEFAULT_BENCH)
            summary = aggregate_package_scores(packages)
        except Exception as exc:  # noqa: BLE001 - keep scoring other arms
            scores.append({"run_dir": str(run_dir), "error": f"{type(exc).__name__}: {exc}"})
            continue
        overall = summary["overall"]
        scores.append(
            {
                "run_dir": str(run_dir),
                "cases_root": str(cases_root),
                "hits": overall["hits"],
                "denominator": overall["denominator"],
                "hit_rate": overall["hit_rate"],
                "size_matched_baseline": overall["mean_size_matched_baseline"],
                "by_role": {
                    role: {
                        "hit_rate": bucket["hit_rate"],
                        "size_matched_baseline": bucket["mean_size_matched_baseline"],
                    }
                    for role, bucket in summary["by_role"].items()
                },
            }
        )
    return scores


def _find_cases_root(run_dir: Path) -> Path | None:
    direct = [path for path in run_dir.glob("case-*") if path.is_dir()]
    if direct:
        return run_dir
    for cases_dir in sorted(run_dir.glob("**/cases")):
        if any(path.is_dir() and path.name.startswith("case-") for path in cases_dir.iterdir()):
            return cases_dir
    nested = [path for path in run_dir.glob("**/case-*") if path.is_dir()]
    if nested:
        return nested[0].parent
    return None


def _write_manifest(output_root: Path, manifest: dict) -> None:
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _write_plan(output_root: Path, planned: list[dict], *, execute: bool) -> None:
    lines = [
        "# Provider-compare plan (DeepSeek vs Qwen3.5-Flash)",
        "",
        f"Mode: `{'execute' if execute else 'dry-run'}`.",
        "",
        "| Provider | Model | Seed | Output |",
        "|---|---|---:|---|",
    ]
    for item in planned:
        lines.append(
            f"| {item['provider']} | `{item['model']}` | {item['seed']} | `{item['run_dir']}` |"
        )
    lines.extend(
        [
            "",
            "Score with size-matched hit@1 after each seed completes.",
            "Do not average DeepSeek and Qwen into one hit rate.",
            "Qwen thinking is disabled (`enable_thinking=false`) for JSON contracts.",
            "",
            "Execute:",
            "```bash",
            "python scripts/run_provider_compare_qwen_20261117.py --execute",
            "```",
            "",
            "Keys required:",
            "- `DEEPSEEK_API_KEY` for the reference arm",
            "- `DASHSCOPE_API_KEY` (or `QWEN_API_KEY`) for Qwen3.5-Flash",
            "",
        ]
    )
    (output_root / "PLAN.md").write_text("\n".join(lines), encoding="utf-8")


def _mirror_docs(output_root: Path) -> None:
    TRACKED.mkdir(parents=True, exist_ok=True)
    for name in ("PLAN.md", "manifest.json", "SCORES.md", "scores.json", "README.md"):
        src = output_root / name
        if src.exists():
            (TRACKED / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _write_score_report(output_root: Path, scores: list[dict]) -> None:
    lines = [
        "# Provider-compare scores (DeepSeek vs Qwen3.5-Flash)",
        "",
        "| Run | Hits | Hit rate | Size-matched baseline |",
        "|---|---:|---:|---:|",
    ]
    for row in scores:
        if "error" in row:
            lines.append(f"| `{row['run_dir']}` | error | | {row['error']} |")
            continue
        lines.append(
            f"| `{Path(row['run_dir']).name}` | {row['hits']}/{row['denominator']} | "
            f"{(row['hit_rate'] or 0)*100:.1f}% | {(row['size_matched_baseline'] or 0)*100:.1f}% |"
        )
    lines.append("")
    (output_root / "SCORES.md").write_text("\n".join(lines), encoding="utf-8")
    (output_root / "scores.json").write_text(
        json.dumps(scores, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
