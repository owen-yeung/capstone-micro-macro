from __future__ import annotations

import asyncio

from src.agent_runtime import AgentRuntime
from src.discussion_context import public_discussion_line
from src.models import AwardResult, EvaluationReport, SimulationState
from src.progress import log as progress_log
from src.prompt_contracts import AWARD_FIELDS, require_fields
from src.prompt_loader import load_prompt
from src.response_recovery import normalize_award
from src.stage_memory import owner_package_memory
from src.state_ops import company_by_role, log_event
from src.verification import submitted_condition_context, conditions


async def make_award_decisions(state: SimulationState, runtime: AgentRuntime) -> None:
    owner = company_by_role(state, "owner")[0]
    owner_agents = state.company_agent_rosters[owner.company_id]
    progress_log(f"award: preparing {len(state.evaluation_report)} package award decisions")
    tasks = [
        _award_task(state, runtime, report, owner, owner_agents, index, len(state.evaluation_report))
        for index, report in enumerate(state.evaluation_report, start=1)
    ]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)
    results = []
    for report, result in zip(state.evaluation_report, raw_results):
        if isinstance(result, Exception):
            runtime.record_recovery(
                "award_no_award_fallback",
                package_id=report.package_id,
                error=f"{type(result).__name__}: {result}",
            )
            result = ([], _no_award(report))
        elif isinstance(result, BaseException):
            raise result
        results.append(result)
    package_awards: list[AwardResult] = []
    for index, (messages, award) in enumerate(results, start=1):
        runtime.import_messages(state, messages)
        package_awards.append(award)
        event = "award_no_valid_bids" if award.selected_bidder_id is None else "award_decision_completed"
        log_event(state, event, {"package_id": award.package_id, "selected_bidder_id": award.selected_bidder_id})
        progress_log(f"award: recorded {index}/{len(results)} {award.package_id} -> {award.selected_bidder_id}")
    state.simulated_award_result = _award_summary(state, package_awards)
    progress_log("award: all package award decisions completed")


async def _award_task(
    state: SimulationState,
    runtime: AgentRuntime,
    report: EvaluationReport,
    owner,
    owner_agents,
    index: int,
    total: int,
) -> tuple[list, AwardResult]:
    progress_log(f"award {report.package_id}: start {index}/{total}")
    local_state = SimulationState()
    local_runtime = runtime.isolated_clone()
    options = [bid for bid in state.bid_documents if bid.package_id == report.package_id]
    await local_runtime.discuss_async(
        local_state,
        "owner_award_decision",
        owner,
        report.package_id,
        owner_agents,
        [(1, "award_risk_review"), (2, "final_award_alignment")],
        _award_discussion_context(report, options),
        owner_package_memory(
            state,
            owner.company_id,
            report.package_id,
            disabled=runtime.ablation.no_cross_stage_memory,
        ),
    )
    if report.recommended_winner is None:
        progress_log(f"award {report.package_id}: no award")
        return local_state.agent_discussion_history, _no_award(report)
    pending = [r for r in conditions(state, owner.company_id, report.package_id, local_state.agent_discussion_history)
               if r["status"] != "verified"]
    data = await runtime.for_entity(owner.company_id).ask_json_async(
        load_prompt("owner", "award.md"),
        "AWARD",
        _award_prompt(report, options, local_state.agent_discussion_history)
        + f"\nOwner clarifications still unresolved: {[r['question'] for r in pending]}\n"
        + "An award recommendation does not complete these checks or form a contract.",
        validator=lambda data: _require_award_response(data, options, report.package_id),
        normalizer=normalize_award,
    )
    selected = data["selected_bidder_id"]
    if selected not in {bid.bidder_id for bid in options}:
        raise ValueError(f"LLM selected unknown bidder_id for {report.package_id}: {selected}")
    bid = next(item for item in options if item.bidder_id == selected)
    final_agent = owner_agents[-1]
    local_runtime.add_message(
        local_state,
        "owner_award_decision",
        3,
        "owner_decision",
        owner,
        report.package_id,
        final_agent,
        "decision",
        data["thoughts"],
        data["content"],
        ["evaluation_report", "opening_record", "bid_documents", "owner_award_discussion"],
        [message.message_id for message in local_state.agent_discussion_history[-4:]],
        "award",
        "final",
        "award",
    )
    progress_log(f"award {report.package_id}: done ({bid.bidder_id})")
    return (
        local_state.agent_discussion_history,
        AwardResult(report.package_id, bid.bidder_id, bid.bidder_name, bid.bidder_type, data["decision_reason"],
                    unresolved_condition_ids=list(dict.fromkeys([*bid.unresolved_condition_ids, *(r["condition_id"] for r in pending)])),
                    bid_assumptions=list(bid.bid_assumptions), pending_clarifications=[r["question"] for r in pending]),
    )


def _require_award_response(data: dict, options: list, package_id: str) -> None:
    require_fields(data, AWARD_FIELDS, "AWARD")
    selected = data["selected_bidder_id"]
    if selected not in {bid.bidder_id for bid in options}:
        raise ValueError(f"LLM selected unknown bidder_id for {package_id}: {selected}")


def _award_discussion_context(report: EvaluationReport, bids: list) -> str:
    return (
        f"Owner is preparing the simulated award decision for {report.package_id}. "
        f"Evaluation recommended {report.recommended_winner}. "
        f"Comparison summary: {report.comparison_summary} "
        f"Owner review notes: {report.owner_review_notes} "
        f"Available bidders: {', '.join(bid.bidder_name for bid in bids) or 'none'}.\n"
        + "\n".join(f"{bid.bidder_id}: {submitted_condition_context(bid)}" for bid in bids)
    )


def _no_award(report: EvaluationReport) -> AwardResult:
    return AwardResult(report.package_id, None, "NO_AWARD", "none", f"No award made: {report.comparison_summary}")


def _award_summary(state: SimulationState, package_awards: list[AwardResult]) -> dict:
    return {
        "project_id": state.project_idea.project_id,
        "package_awards": [award.__dict__ for award in package_awards],
        "overall_award_summary": "Owner completed independent package-level award decisions.",
        "selected_companies": sorted({award.selected_bidder_id for award in package_awards if award.bidder_type == "company"}),
        "selected_consortiums": sorted({award.selected_bidder_id for award in package_awards if award.bidder_type == "consortium"}),
        "handoff_to_project_execution": "project_execution_log.json",
    }


def _award_prompt(report: EvaluationReport, bids: list, discussion: list) -> str:
    options = "\n".join(_bid_option(bid) for bid in bids)
    evaluations = "\n".join(_evaluation_line(item) for item in report.bid_evaluations)
    owner_discussion = "\n".join(
        f"- {public_discussion_line(msg)}"
        for msg in discussion[-6:]
    )
    return (
        f"Package: {report.package_id}\nAward options:\n{options}\n"
        f"Evaluation recommended winner: {report.recommended_winner}\n"
        f"Evaluation summary: {report.comparison_summary}\n"
        f"Owner review notes: {report.owner_review_notes}\n"
        f"Owner award discussion:\n{owner_discussion}\n"
        f"Bid evaluations:\n{evaluations}"
    )


def _bid_option(bid) -> str:
    return (
        f"- {bid.bidder_id}: {bid.bidder_name}, type={bid.bidder_type}, quotation={bid.quotation}\n"
        f"  technical_proposal: {bid.technical_proposal}\n"
        f"  risk_response: {bid.risk_response}\n"
        f"  submission_summary: {bid.submission_summary}\n"
        f"  {submitted_condition_context(bid)}"
    )


def _evaluation_line(item: dict) -> str:
    return (
        f"- {item.get('bidder_id')}: technical={item.get('technical_view')}; "
        f"cost={item.get('cost_view')}; owner_control={item.get('owner_control_view')}; "
        f"strengths={item.get('strengths')}; concerns={item.get('concerns')}"
    )
