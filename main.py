from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

from src.ablation import ABLATION_IDS, AblationConfig
from src.async_policy import install_asyncio_policy
from src.case_sources import DEFAULT_CONFIG, list_case_ids, load_case_config, load_case_inputs
from src.mock_llm import MockLLMClient
from src.progress import set_log_path
from src.run_audit import BatchRunTracker, LLMCallAuditLogger, write_case_error, write_case_status
from src.workflow import TenderSimulationWorkflow
from src.workflow_checkpoint import WorkflowCheckpointStore
from src.writers import missing_required_outputs, write_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run codedemo_v2 tender simulation.")
    parser.add_argument(
        "--project-idea",
        default="",
        help="Optional rough owner intent. If omitted, a simple generator agent creates the initial project idea.",
    )
    parser.add_argument(
        "--case-id",
        default="",
        help="Run one configured validation case from the test source CSV files, such as CASE-0005.",
    )
    parser.add_argument(
        "--run-config",
        action="store_true",
        help="Use the run.scope setting from the JSON config file.",
    )
    parser.add_argument(
        "--run-scope",
        choices=["manual", "single", "batch", "all"],
        default="manual",
        help="Case-data run scope. single, batch, and all use configured case test sources.",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Shortcut for --run-scope batch.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="JSON config for case and batch validation runs.",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=0,
        help="Optional limit for --batch runs. 0 means no extra limit.",
    )
    parser.add_argument(
        "--mode",
        choices=["case", "ai"],
        default="case",
        help="case uses configured project/enterprise test sources; ai lets the LLM generate project and company inputs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("result"),
        help="Base output directory. Each run writes result/run_<timestamp>/.",
    )
    parser.add_argument(
        "--profile",
        choices=["full", "smoke"],
        default="full",
        help="full runs all MVP agents; smoke runs a smaller workflow for real LLM prompt testing.",
    )
    parser.add_argument(
        "--ablation",
        choices=["none", *ABLATION_IDS],
        default="none",
        help=(
            "Interim §5.5 single-mechanism ablation: A1 single-agent firm, "
            "A2 rule consortium without negotiation, A3 no reconsideration, "
            "A4 no cross-stage memory. Real model runs still need a fresh authorized scope."
        ),
    )
    parser.add_argument(
        "--llm-provider",
        default="",
        help=(
            "Override LLM_PROVIDER for this run (deepseek, qwen, groq, openai, or other "
            "OpenAI-compatible id). Empty keeps the environment default."
        ),
    )
    parser.add_argument(
        "--llm-model",
        default="",
        help="Override the provider model name for this run. Empty keeps the provider default.",
    )
    parser.add_argument(
        "--resume-batch",
        type=Path,
        default=None,
        help="Resume a prior batch directory, skipping cases already marked succeeded.",
    )
    parser.add_argument(
        "--resume-run",
        type=Path,
        default=None,
        help="Resume one failed or interrupted case from its latest durable workflow checkpoint.",
    )
    args = parser.parse_args()
    if args.resume_batch and args.resume_run:
        parser.error("--resume-batch and --resume-run cannot be combined.")
    if args.mode == "ai" and (args.case_id or args.run_config or args.batch or args.run_scope != "manual" or args.max_cases):
        parser.error("--case-id, --run-config, --run-scope, --batch, and --max-cases are only valid with --mode case.")
    return args


def main() -> int:
    install_asyncio_policy()
    args = parse_args()
    tracker = BatchRunTracker.resume(args.resume_batch) if args.resume_batch else None
    resume_attempt = 1
    if args.resume_run is not None:
        args.resume_run = args.resume_run.resolve()
        status_path = args.resume_run / "case_status.json"
        if not status_path.exists():
            raise FileNotFoundError(f"Case status not found for resumed run: {status_path}")
        prior_status = json.loads(status_path.read_text(encoding="utf-8"))
        if prior_status.get("status") not in {"failed", "interrupted"}:
            raise ValueError(f"Only failed or interrupted runs can resume: {prior_status.get('status')}")
        args.case_id = str(prior_status.get("case_id") or "")
        args.mode = str(prior_status.get("mode") or args.mode)
        args.profile = str(prior_status.get("profile") or args.profile)
        if prior_status.get("config_path"):
            args.config = Path(prior_status["config_path"])
        resume_attempt = int(prior_status.get("attempt", 1)) + 1
    if tracker is not None:
        args.profile = tracker.profile
        args.mode = tracker.manifest["mode"]
        args.config = Path(tracker.manifest["config_path"])
    llm = _build_llm_client(args)
    needs_config = args.mode == "case" or args.case_id or args.batch or args.run_config or args.run_scope != "manual"
    config = load_case_config(args.config) if needs_config else {}
    if tracker is not None:
        case_ids = tracker.remaining_case_ids()
    else:
        case_ids = _case_ids(args, config)
    if args.mode == "case" and not case_ids and tracker is None:
        raise ValueError("Case mode needs a case id. Set --case-id, --run-config, or config.run.scope/single_case_id.")
    requested_scope = _run_scope(args, config)
    is_batch = tracker is not None or (
        bool(case_ids) and not args.case_id and requested_scope in {"batch", "all"}
    )
    if is_batch and tracker is None:
        tracker = BatchRunTracker.create(
            args.output_dir,
            case_ids,
            mode=args.mode,
            profile=args.profile,
            config_path=args.config,
        )
    if tracker is not None:
        print(f"Batch directory: {tracker.batch_dir}")
        print(f"Cases remaining: {len(case_ids)}")
        interrupted = False
        try:
            for case_id in case_ids:
                run_dir = tracker.start_case(case_id)
                attempt = tracker.manifest["cases"][case_id]["attempts"]
                try:
                    _run_once(args, llm, case_id=case_id, config=config, run_dir=run_dir, attempt=attempt)
                except KeyboardInterrupt as exc:
                    tracker.fail_case(case_id, exc, interrupted=True)
                    interrupted = True
                    raise
                except Exception as exc:
                    tracker.fail_case(case_id, exc)
                    print(f"Case failed: {case_id}: {type(exc).__name__}: {exc}", file=sys.stderr)
                    continue
                status_path = run_dir / "case_status.json"
                case_status = (
                    json.loads(status_path.read_text(encoding="utf-8"))["status"]
                    if status_path.exists()
                    else "succeeded"
                )
                tracker.complete_case(case_id, case_status)
        finally:
            tracker.finalize(interrupted=interrupted)
        failed = tracker.manifest["counts"].get("failed", 0)
        incomplete = failed + tracker.manifest["counts"].get("interrupted", 0)
        print(f"Batch status: {tracker.manifest['status']}")
        print(f"Batch manifest: {tracker.manifest_path}")
        return 1 if incomplete else 0
    if case_ids:
        _run_once(
            args,
            llm,
            case_id=case_ids[0],
            config=config,
            run_dir=args.resume_run,
            attempt=resume_attempt,
        )
    else:
        _run_once(args, llm, run_dir=args.resume_run, attempt=resume_attempt)
    return 0


def _build_llm_client(args: argparse.Namespace | None = None):
    if os.getenv("CODEDEMO_USE_LOCAL_TEST_CLIENT", "").strip() == "1":
        return MockLLMClient()
    # Lazy import keeps mock/local wiring usable without langchain installed.
    from src.llm_client import OpenAICompatibleClient

    provider = getattr(args, "llm_provider", "") if args is not None else ""
    model = getattr(args, "llm_model", "") if args is not None else ""
    return OpenAICompatibleClient.from_env(
        provider=provider or None,
        model=model or None,
    )


def _case_ids(args: argparse.Namespace, config: dict) -> list[str]:
    if args.mode == "ai":
        return []
    scope = _run_scope(args, config)
    if scope == "batch":
        case_ids = list(config.get("batch_case_ids", []))
        max_cases = args.max_cases or int(config.get("run", {}).get("max_cases", 0) or 0)
        if max_cases:
            case_ids = case_ids[:max_cases]
        return case_ids
    if scope == "all":
        case_ids = list_case_ids(config)
        max_cases = args.max_cases or int(config.get("run", {}).get("max_cases", 0) or 0)
        if max_cases:
            case_ids = case_ids[:max_cases]
        return case_ids
    if scope == "single":
        case_id = args.case_id or config.get("run", {}).get("single_case_id") or config.get("default_case_id", "")
        if not case_id:
            raise ValueError("No single case id found. Set --case-id or config.run.single_case_id.")
        return [case_id]
    if args.case_id:
        return [args.case_id]
    return []


def _run_scope(args: argparse.Namespace, config: dict) -> str:
    if args.batch:
        return "batch"
    if args.run_scope != "manual":
        return args.run_scope
    if args.run_config:
        return config.get("run", {}).get("scope", "single")
    if args.case_id:
        return "single"
    if args.mode == "case":
        return config.get("run", {}).get("scope", "single")
    return "manual"


def _run_once(
    args: argparse.Namespace,
    llm,
    case_id: str = "",
    config: dict | None = None,
    run_dir: Path | None = None,
    attempt: int = 1,
) -> Path:
    if run_dir is None:
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        suffix = f"_{case_id.lower()}" if case_id else ""
        run_dir = args.output_dir / f"run_{timestamp}{suffix}"
    run_dir.mkdir(parents=True, exist_ok=True)
    audit_logger = LLMCallAuditLogger(run_dir, case_id, llm, attempt=attempt)
    checkpoint_store = WorkflowCheckpointStore(run_dir, case_id, args.profile)
    set_log_path(run_dir / "progress.log")
    write_case_status(
        run_dir,
        status="running",
        case_id=case_id or None,
        attempt=attempt,
        mode=args.mode,
        profile=args.profile,
        config_path=str(args.config.resolve()) if getattr(args, "config", None) else None,
        checkpoint=checkpoint_store.summary(),
        started_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds"),
    )
    workflow = None
    try:
        ablation = AblationConfig.from_id(getattr(args, "ablation", "none"))
        workflow = TenderSimulationWorkflow(
            llm,
            profile=args.profile,
            audit_logger=audit_logger,
            checkpoint_store=checkpoint_store,
            ablation=ablation,
        )
        project_idea = None
        companies = None
        validation_context = {}
        llm_meta = _llm_metadata(llm)
        if case_id:
            project_idea, companies, validation_context = load_case_inputs(config or {}, case_id)
            validation_context["run_mode"] = args.mode
            validation_context["profile"] = args.profile
            validation_context["ablation"] = ablation.to_dict()
            validation_context["llm"] = llm_meta
        state = workflow.run(
            project_prompt=None if case_id else (args.project_idea or None),
            project_idea=project_idea,
            companies=companies,
        )
        if validation_context:
            state.validation_context = {**validation_context, **state.validation_context}
        else:
            extras = {"llm": llm_meta}
            if ablation.active_ids():
                extras["ablation"] = ablation.to_dict()
            state.validation_context = {**state.validation_context, **extras}
        output_files = write_outputs(state, run_dir)
        missing = missing_required_outputs(run_dir)
        if missing:
            raise RuntimeError(f"Missing required output files: {missing}")
        reliability = workflow.runtime.reliability_summary()
        final_status = reliability["status"]
        write_case_status(
            run_dir,
            status=final_status,
            completed_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds"),
            output_files=output_files,
            discussion_messages=len(state.agent_discussion_history),
            bid_documents=len(state.bid_documents),
            award_packages=len(state.simulated_award_result.get("package_awards", [])),
            reliability=reliability,
            checkpoint=checkpoint_store.summary(),
            error=None,
        )
    except BaseException as exc:
        reliability = (
            workflow.runtime.reliability_summary()
            if workflow is not None
            else _reliability_summary(audit_logger.recovery_events())
        )
        write_case_error(run_dir, exc, attempt=attempt)
        write_case_status(
            run_dir,
            status="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
            completed_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds"),
            error=f"{type(exc).__name__}: {exc}",
            checkpoint=checkpoint_store.summary(),
            reliability=reliability,
        )
        raise
    finally:
        set_log_path(None)
    print("codedemo_v2 simulation completed")
    print(f"Mode: {args.mode}")
    print(f"Profile: {args.profile}")
    print(f"Ablation: {','.join(ablation.active_ids()) or 'none'}")
    print(f"LLM: {_llm_metadata(llm).get('provider')}/{_llm_metadata(llm).get('model')}")
    if case_id:
        print(f"Case id: {case_id}")
        print(f"Candidate companies: {len(companies or [])}")
    if os.getenv("CODEDEMO_USE_LOCAL_TEST_CLIENT", "").strip() != "1":
        print(f"LLM concurrency: {workflow.runtime.throttle.limit}")
        print(f"LLM min interval: {workflow.runtime.throttle.min_interval}")
    print(f"Run directory: {run_dir}")
    print(f"Discussion messages: {len(state.agent_discussion_history)}")
    print(f"Bid documents: {len(state.bid_documents)}")
    print(f"Award packages: {len(state.simulated_award_result.get('package_awards', []))}")
    print(f"Final report: {output_files['final_report']}")
    return run_dir


def _reliability_summary(events: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for event in events:
        kind = str(event.get("kind", "unknown"))
        counts[kind] = counts.get(kind, 0) + 1
    return {
        "status": "degraded" if events else "succeeded",
        "recovery_count": len(events),
        "recovery_counts": counts,
    }


def _llm_metadata(llm) -> dict[str, str | None]:
    config = getattr(llm, "config", None)
    if config is None:
        return {"provider": "mock", "model": "mock"}
    return {
        "provider": getattr(config, "provider", None),
        "model": getattr(config, "model", None),
        "base_url": getattr(config, "base_url", None),
    }


if __name__ == "__main__":
    raise SystemExit(main())
