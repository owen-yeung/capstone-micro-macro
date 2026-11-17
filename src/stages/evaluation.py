from __future__ import annotations

import asyncio

from src.agent_runtime import AgentRuntime
from src.evaluation_contracts import require_owner_evaluation_shape
from src.discussion_context import public_discussion_line
from src.models import DiscussionMessage, EvaluationReport, SimulationState, TenderPackage
from src.progress import log as progress_log
from src.prompt_loader import load_prompt
from src.response_recovery import normalize_evaluation
from src.stage_memory import owner_package_memory
from src.state_ops import company_by_role, log_event
from src.verification import submitted_condition_context


async def evaluate_bids(state: SimulationState, runtime: AgentRuntime) -> None:
    owner = company_by_role(state, "owner")[0]
    owner_agents = state.company_agent_rosters[owner.company_id]
    evaluators = [agent.agent_id for agent in owner_agents]
    progress_log(f"evaluation: preparing {len(state.tender_packages)} package evaluation tasks")
    raw_results = await asyncio.gather(
        *[_evaluation_task(state, runtime, package, owner, owner_agents, evaluators) for package in state.tender_packages],
        return_exceptions=True,
    )
    results = []
    for package, result in zip(state.tender_packages, raw_results):
        if isinstance(result, Exception):
            runtime.record_recovery(
                "evaluation_no_award_fallback",
                package_id=package.package_id,
                error=f"{type(result).__name__}: {result}",
            )
            result = (
                [],
                EvaluationReport(
                    package.package_id,
                    evaluators,
                    [],
                    "Degraded fallback: evaluation output could not be validated.",
                    None,
                    "No award recommendation was made; manual review or retendering is required.",
                ),
            )
        elif isinstance(result, BaseException):
            raise result
        results.append(result)
    for index, (messages, report) in enumerate(results, start=1):
        runtime.import_messages(state, messages)
        state.evaluation_report.append(report)
        event = "evaluation_no_bids" if report.recommended_winner is None else "evaluation_completed"
        log_event(state, event, {"package_id": report.package_id, "recommended_winner": report.recommended_winner})
        progress_log(f"evaluation: recorded {index}/{len(results)} {report.package_id} -> {report.recommended_winner}")


async def _evaluation_task(
    state: SimulationState,
    runtime: AgentRuntime,
    package: TenderPackage,
    owner,
    owner_agents,
    evaluators: list[str],
) -> tuple[list, EvaluationReport]:
    progress_log(f"evaluation {package.package_id}: start")
    local_state = SimulationState()
    local_runtime = runtime.isolated_clone()
    bids = [bid for bid in state.bid_documents if bid.package_id == package.package_id]
    progress_log(f"evaluation {package.package_id}: {len(bids)} bids to review")
    await local_runtime.discuss_async(
        local_state,
        "evaluation",
        owner,
        package.package_id,
        owner_agents,
        [(1, "department_evaluation"), (2, "comparative_review")],
        f"Owner evaluates bids for {package.package_name}.\n"
        + "\n".join(f"{bid.bidder_id}: {submitted_condition_context(bid)}" for bid in bids),
        owner_package_memory(
            state,
            owner.company_id,
            package.package_id,
            disabled=runtime.ablation.no_cross_stage_memory,
        ),
    )
    if not bids:
        progress_log(f"evaluation {package.package_id}: done (no bids)")
        return local_state.agent_discussion_history, EvaluationReport(
            package.package_id,
            evaluators,
            [],
            "No bids were submitted for this package, so the owner cannot recommend a bidder.",
            None,
            "Owner should retender, revise scope, or clarify requirements before making an award.",
        )
    data = await runtime.for_entity(owner.company_id).ask_json_async(
        load_prompt("owner", "evaluation.md"),
        "EVALUATION",
        _evaluation_prompt(state, package, bids, local_state.agent_discussion_history),
        validator=lambda data: _require_evaluation_response(data, bids, package.package_id),
        normalizer=normalize_evaluation,
    )
    recommended = data["recommended_bidder_id"]
    if recommended not in {bid.bidder_id for bid in bids}:
        raise ValueError(f"LLM recommended unknown bidder_id for {package.package_id}: {recommended}")
    report = EvaluationReport(
        package.package_id,
        evaluators,
        data["bid_evaluations"],
        data["comparison_summary"],
        recommended,
        data["owner_review_notes"],
    )
    progress_log(f"evaluation {package.package_id}: done ({recommended})")
    return local_state.agent_discussion_history, report


def _require_evaluation_response(data: dict, bids: list, package_id: str) -> None:
    require_owner_evaluation_shape(data)
    recommended = data["recommended_bidder_id"]
    if recommended not in {bid.bidder_id for bid in bids}:
        raise ValueError(f"LLM recommended unknown bidder_id for {package_id}: {recommended}")


def _evaluation_prompt(
    state: SimulationState,
    package: TenderPackage,
    bids: list,
    evaluation_messages: list[DiscussionMessage] | None = None,
) -> str:
    bid_blocks = []
    for bid in bids:
        bid_blocks.append(
            "\n".join(
                [
                    f"bid_id: {bid.bid_id}",
                    f"bidder_id: {bid.bidder_id}",
                    f"bidder_name: {bid.bidder_name}",
                    f"bidder_type: {bid.bidder_type}",
                    f"quotation: {bid.quotation}",
                    f"quotation_breakdown: {bid.quotation_breakdown}",
                    f"technical_proposal: {bid.technical_proposal}",
                    f"implementation_plan: {bid.implementation_plan}",
                    f"schedule_commitment: {bid.schedule_commitment}",
                    f"owner_control_response: {bid.compliance_statement}",
                    f"risk_response: {bid.risk_response}",
                    f"submission_summary: {bid.submission_summary}",
                    submitted_condition_context(bid),
                ]
            )
        )
    owner_messages = [
        msg
        for msg in state.agent_discussion_history
        if msg.stage in {"owner_requirement_refinement", "bid_opening", "evaluation"} and msg.package_id in {"", package.package_id}
    ]
    seen = {msg.message_id for msg in owner_messages}
    owner_messages.extend(msg for msg in evaluation_messages or [] if msg.message_id not in seen)
    owner_discussion = [public_discussion_line(msg) for msg in owner_messages]
    return (
        f"Package id: {package.package_id}\nPackage name: {package.package_name}\nScope: {package.scope}\n"
        f"Required role: {package.required_company_role}\n"
        f"Package capability needs: {package.qualification_requirements}\n"
        f"Owner bid content asks: {package.proposal_requirements}\n"
        f"Owner comparison focus: {package.evaluation_criteria}\n"
        f"Owner decision policy: {package.owner_decision_policy}\n\n"
        f"Owner discussion:\n" + "\n".join(f"- {item}" for item in owner_discussion[-8:]) + "\n\n"
        f"Bids:\n\n" + "\n\n---\n\n".join(bid_blocks)
    )
