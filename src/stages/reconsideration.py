from __future__ import annotations

import asyncio

from src.agent_runtime import AgentRuntime
from src.discussion_context import public_discussion_line
from src.models import Company, ParticipationDecision, SimulationState, TenderPackage
from src.verification import conditions, evidence_context, guarded_validator, disposition_fields, DecisionOutputError, output_verification_requests
from src.company_grounding import company_evidence
from src.task_role_contract import role_context
from src.progress import log as progress_log
from src.prompt_contracts import require_management_decision
from src.prompt_loader import load_prompt
from src.response_recovery import normalize_management_decision
from src.stage_memory import company_package_memory
from src.state_ops import company_by_id, final_agent, log_event, package_by_id


async def reconsider_after_failed_consortiums(state: SimulationState, runtime: AgentRuntime) -> None:
    # A3: remove reconsideration after consortium failure.
    if runtime.ablation.no_reconsideration:
        progress_log("reconsideration: skipped by ablation A3")
        log_event(state, "reconsideration_skipped_ablation_a3", {"candidate_count": len(_candidates(state))})
        return
    candidates = _candidates(state)
    progress_log(f"reconsideration: preparing {len(candidates)} failed-consortium decisions")
    raw_results = await asyncio.gather(
        *[_task(state, runtime, decision, package, company) for decision, package, company in candidates],
        return_exceptions=True,
    )
    results = []
    for (decision, package, company), result in zip(candidates, raw_results):
        if isinstance(result, Exception):
            if runtime.company_narrative_grounding:
                runtime.import_messages(state,getattr(result,'discussion_messages',[]))
                pending={'company_id':company.company_id,'package_id':package.package_id,
                    'status':'output_validation_pending_not_business_no_bid','error':str(result),
                    'attempts':getattr(result,'output_attempts',[]),'review':getattr(result,'output_review',None)}
                state.validation_context.setdefault('micro_output_pending',[]).append(pending)
                runtime.record_recovery('reconsideration_output_pending',**pending)
                continue
            runtime.record_recovery(
                "reconsideration_conservative_fallback",
                company_id=company.company_id,
                package_id=package.package_id,
                error=f"{type(result).__name__}: {result}",
            )
            result = (
                getattr(result, "discussion_messages", []),
                decision,
                ParticipationDecision(
                    company.company_id,
                    package.package_id,
                    "no_bid",
                    "Degraded fallback: reconsideration could not be validated.",
                    unresolved_condition_ids=getattr(result, "unresolved_condition_ids", decision.unresolved_condition_ids),
                ),
            )
        elif isinstance(result, BaseException):
            raise result
        results.append(result)
    for index, (messages, old_decision, new_decision) in enumerate(results, start=1):
        runtime.import_messages(state, messages)
        old_decision.decision = new_decision.decision
        old_decision.reason = new_decision.reason
        for key, value in disposition_fields(new_decision.__dict__).items():
            setattr(old_decision, key, value)
        log_event(state, "bid_participation_reconsidered", new_decision.__dict__)
        progress_log(
            f"reconsideration: recorded {index}/{len(results)} "
            f"{new_decision.company_id} -> {new_decision.package_id}: {new_decision.decision}"
        )


def _candidates(state: SimulationState) -> list[tuple[ParticipationDecision, TenderPackage, Company]]:
    items = []
    for decision in state.participation_decisions:
        if decision.decision != "bid_with_consortium":
            continue
        formed = any(decision.company_id in item.member_company_ids and item.package_id == decision.package_id for item in state.consortiums)
        if not formed:
            items.append((decision, package_by_id(state, decision.package_id), company_by_id(state, decision.company_id)))
    return items


async def _task(
    state: SimulationState,
    runtime: AgentRuntime,
    decision: ParticipationDecision,
    package: TenderPackage,
    company: Company,
) -> tuple[list, ParticipationDecision, ParticipationDecision]:
    progress_log(f"reconsideration {company.company_id}/{package.package_id}: start")
    local_state = SimulationState()
    local_runtime = runtime.isolated_clone()
    agents = state.company_agent_rosters[company.company_id]
    await local_runtime.discuss_async(
        local_state,
        "consortium_failure_reconsideration",
        company,
        package.package_id,
        agents,
        [(1, "failed_consortium_reconsideration"), (2, "final_reconsideration")],
        _reconsideration_context(company, package) + "\n" + evidence_context(conditions(state, company.company_id, package.package_id)),
        company_package_memory(
            state,
            company.company_id,
            package.package_id,
            {"bid_participation_decision", "consortium_formation"},
            disabled=runtime.ablation.no_cross_stage_memory,
        ),
    )
    manager = final_agent(agents)
    records = conditions(state, company.company_id, package.package_id, local_state.agent_discussion_history)
    sources = company_evidence(company) if runtime.company_grounding else None
    try:
        data = await runtime.for_entity(company.company_id).ask_json_async(
            load_prompt("company", "reconsider_after_consortium.md"),
            "RECONSIDER_AFTER_CONSORTIUM",
            _prompt(state, local_state, company, package, decision) + "\n" + evidence_context(records, company_sources=sources, narrative_grounding=runtime.company_narrative_grounding) + (role_context(company.company_role) if runtime.task_role_grounding else ""),
            validator=guarded_validator(_require_reconsideration_decision, records, company_sources=sources, narrative_grounding=runtime.company_narrative_grounding, task_role=company.company_role if runtime.task_role_grounding else None),
            normalizer=normalize_management_decision,
        )
    except Exception as exc:
        raise DecisionOutputError(exc, local_state.agent_discussion_history, records) from exc
    local_runtime.add_message(
        local_state,
        "consortium_failure_reconsideration",
        3,
        "management_reconsideration",
        company,
        package.package_id,
        manager,
        "decision",
        data.get("thoughts", ""),
        data["content"],
        ["failed_consortium", "tender_package", "company_profile", "internal_discussion"],
        [],
        data["decision"],
        "final",
        data["decision"],
        verification_requests=output_verification_requests(data),
    )
    final_records = conditions(state, company.company_id, package.package_id, local_state.agent_discussion_history)
    new_decision = ParticipationDecision(company.company_id, package.package_id, data["decision"], data["reason"], **disposition_fields(data, final_records))
    progress_log(f"reconsideration {company.company_id}/{package.package_id}: done ({new_decision.decision})")
    return local_state.agent_discussion_history, decision, new_decision


def _require_reconsideration_decision(data: dict) -> None:
    require_management_decision(data)
    if data["decision"] not in {"bid", "no_bid"}:
        raise ValueError(f"RECONSIDER_AFTER_CONSORTIUM invalid decision: {data['decision']}")


def _reconsideration_context(company: Company, package: TenderPackage) -> str:
    return (
        f"The consortium option failed for {company.company_name}. Reconsider whether to bid alone or withdraw.\n"
        f"Package scope: {package.scope}\n"
        f"Capability needs: {package.qualification_requirements}\n"
        f"A solo bid may still use ordinary consultants, subconsultants, subcontractors, suppliers, or short-term support "
        f"if {company.company_name} can remain the single accountable bidder and manage the interfaces credibly. "
        f"Discuss whether external support is a manageable delivery model or whether the missing partner creates a true "
        f"accountability gap that should lead to withdrawal."
    )


def _prompt(state: SimulationState, local_state: SimulationState, company: Company, package: TenderPackage, decision: ParticipationDecision) -> str:
    discussion = [
        public_discussion_line(msg)
        for msg in local_state.agent_discussion_history
        if msg.stage == "consortium_failure_reconsideration"
    ]
    consortium_notes = [
        public_discussion_line(msg)
        for msg in state.agent_discussion_history
        if msg.stage == "consortium_formation" and msg.package_id == package.package_id
        and (msg.company_id == company.company_id or msg.message_type == "negotiation")
    ]
    return (
        f"Company id: {company.company_id}\nCompany name: {company.company_name}\nRole: {company.company_role}\n"
        f"Profile: {company.profile}\nStrengths: {company.strengths}\nWeaknesses: {company.weaknesses}\n"
        f"Capabilities: {company.qualifications}\nCapacity: {company.capacity}\nRisk signals: {company.risk_signals}\n"
        f"Package id: {package.package_id}\nPackage name: {package.package_name}\nScope: {package.scope}\n"
        f"Package capability needs: {package.qualification_requirements}\nOriginal decision: {decision.decision}; reason: {decision.reason}\n"
        f"Consortium outcome: no consortium was formed for this company and package.\n"
        f"Consortium discussion:\n" + "\n".join(f"- {item}" for item in consortium_notes[-8:]) + "\n"
        f"Reconsideration discussion:\n" + "\n".join(f"- {item}" for item in discussion[-8:])
    )
