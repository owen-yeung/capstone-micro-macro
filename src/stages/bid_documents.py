from __future__ import annotations

import asyncio

from src.agent_runtime import AgentRuntime
from src.discussion_context import public_discussion_line
from src.models import BidDocument, Company, DiscussionMessage, ParticipationDecision, SimulationState, TenderPackage
from src.progress import log as progress_log
from src.prompt_contracts import require_bid_document_shape
from src.prompt_loader import load_prompt
from src.response_recovery import normalize_bid_document
from src.stages.bid_prompt_context import bid_decisions, bid_document_discussion_context, bidder_context, competition_context, company_context
from src.stage_memory import company_package_memory
from src.state_ops import company_by_id, log_event, package_by_id, final_agent
from src.verification import conditions, evidence_context, guarded_validator, disposition_fields, DecisionOutputError, output_verification_requests
from src.company_grounding import company_evidence
from src.task_role_contract import role_context


async def generate_bid_documents(state: SimulationState, runtime: AgentRuntime) -> None:
    candidates = []
    for decision in state.participation_decisions:
        lead_consortium = _lead_consortium(state, decision.company_id, decision.package_id)
        if decision.decision == "no_bid":
            continue
        if not lead_consortium and _is_non_lead_consortium_member(state, decision.company_id, decision.package_id):
            continue
        if decision.decision == "bid_with_consortium" and not lead_consortium:
            log_event(state, "bid_not_submitted_consortium_unformed", {"company_id": decision.company_id, "package_id": decision.package_id})
            continue
        member_ids = lead_consortium.member_company_ids if lead_consortium else [decision.company_id]
        blocking = [r for member_id in member_ids for r in conditions(state, member_id, decision.package_id)
                    if r["required_before_submission"] and r["status"] != "verified"]
        if blocking:
            log_event(state, "bid_submission_pending_verification", {
                "company_id": decision.company_id, "package_id": decision.package_id,
                "condition_ids": [r["condition_id"] for r in blocking],
            })
            continue
        package = package_by_id(state, decision.package_id)
        company = company_by_id(state, decision.company_id)
        candidates.append((decision, package, company))
    progress_log(f"bid_documents: preparing {len(candidates)} bid document tasks")
    raw_results = await asyncio.gather(
        *[_bid_task(state, runtime, decision, package, company) for decision, package, company in candidates],
        return_exceptions=True,
    )
    results = []
    for (decision, package, company), result in zip(candidates, raw_results):
        if isinstance(result, Exception):
            runtime.import_messages(state, getattr(result, "discussion_messages", []))
            if runtime.company_narrative_grounding:
                pending={'company_id':company.company_id,'package_id':package.package_id,
                    'status':'output_validation_pending_not_submitted','error':str(result),
                    'attempts':getattr(result,'output_attempts',[]),'review':getattr(result,'output_review',None)}
                state.validation_context.setdefault('micro_output_pending',[]).append(pending)
                runtime.record_recovery('bid_output_pending',**pending)
                continue
            runtime.record_recovery(
                "bid_submission_skipped",
                company_id=company.company_id,
                package_id=package.package_id,
                error=f"{type(result).__name__}: {result}",
            )
            progress_log(f"bid_document {company.company_id}/{package.package_id}: skipped after failure")
            continue
        if isinstance(result, BaseException):
            raise result
        results.append(result)
    counters: dict[str, int] = {}
    for index, (messages, bid) in enumerate(results, start=1):
        runtime.import_messages(state, messages)
        if bid is None:
            # New prerequisites raised during drafting are retained, not lost as
            # a technical failure or silently converted to a no_bid decision.
            log_event(state, "bid_submission_pending_verification", {
                "company_id": messages[0].company_id, "package_id": messages[0].package_id,
            })
            continue
        counters[bid.package_id] = counters.get(bid.package_id, 0) + 1
        bid.bid_id = f"bid_{bid.package_id}_{counters[bid.package_id]:03d}"
        state.bid_documents.append(bid)
        log_event(state, "bid_document_submitted", {"package_id": bid.package_id, "bidder_id": bid.bidder_id})
        progress_log(f"bid_documents: recorded {index}/{len(results)} {bid.bidder_id} -> {bid.package_id}")


async def _bid_task(
    state: SimulationState,
    runtime: AgentRuntime,
    decision: ParticipationDecision,
    package: TenderPackage,
    company: Company,
) -> tuple[list, BidDocument | None]:
    progress_log(f"bid_document {company.company_id}/{package.package_id}: start")
    local_state = SimulationState()
    local_runtime = runtime.isolated_clone()
    consortium = _lead_consortium(state, decision.company_id, decision.package_id)
    bidder_type = "consortium" if consortium else "company"
    bidder_id = consortium.consortium_id if consortium else company.company_id
    bidder_name = consortium.consortium_name if consortium else company.company_name
    await local_runtime.discuss_async(
        local_state,
        "bid_document_generation",
        company,
        package.package_id,
        state.company_agent_rosters[company.company_id],
        [(1, "section_drafting"), (2, "internal_review"), (3, "final_submission")],
        bid_document_discussion_context(package, decision, consortium, bidder_name)
        + "\nYour documented company context:\n" + company_context(company)
        + f"\nPackage scope: {package.scope}\nCapability needs: {package.qualification_requirements}\n"
        + evidence_context(conditions(state, company.company_id, package.package_id)),
        company_package_memory(
            state,
            company.company_id,
            package.package_id,
            {"bid_participation_decision", "consortium_formation", "consortium_failure_reconsideration"},
            disabled=runtime.ablation.no_cross_stage_memory,
        ),
    )
    records = conditions(state, company.company_id, package.package_id, local_state.agent_discussion_history)
    if any(r["required_before_submission"] and r["status"] != "verified" for r in records):
        return local_state.agent_discussion_history, None
    try:
        sources = company_evidence(company) if runtime.company_grounding else None
        data = await runtime.for_entity(company.company_id).ask_json_async(
            load_prompt("company", "bid_document.md"),
            "BID_DOCUMENT",
            _bid_prompt(state, bidder_id, bidder_name, bidder_type, package.package_id, local_state.agent_discussion_history)
            + "\n" + evidence_context(records, company_sources=sources, narrative_grounding=runtime.company_narrative_grounding) + (role_context(company.company_role) if runtime.task_role_grounding else ""),
            validator=guarded_validator(_require_bid_response, records, submission=True, company_sources=sources, narrative_grounding=runtime.company_narrative_grounding, task_role=company.company_role if runtime.task_role_grounding else None),
            normalizer=normalize_bid_document,
        )
    except Exception as exc:
        raise DecisionOutputError(exc, local_state.agent_discussion_history, records) from exc
    final_requests = output_verification_requests(data)
    if final_requests:
        # A prerequisite first raised in the final draft must survive checkpoint
        # and delay submission just like one raised by a department discussion.
        local_runtime.add_message(local_state, 'bid_document_generation', 4, 'final_draft_conditions',
            company, package.package_id, final_agent(state.company_agent_rosters[company.company_id]),
            'decision', '', '\n'.join(final_requests[i]['question'] for i in range(len(final_requests))),
            ['final_bid_draft'], [], '', 'pending checks', '', verification_requests=final_requests)
        records = conditions(state, company.company_id, package.package_id, local_state.agent_discussion_history)
        if any(r['required_before_submission'] and r['status'] != 'verified' for r in records):
            return local_state.agent_discussion_history, None
    bid = BidDocument(
        "",
        package.package_id,
        bidder_type,
        bidder_id,
        bidder_name,
        data["technical_proposal"],
        data["implementation_plan"],
        float(data["quotation"]),
        data["schedule_commitment"],
        data["owner_control_response"],
        data["risk_response"],
        data["submission_summary"],
        data["quotation_breakdown"],
        **disposition_fields(data, records),
    )
    progress_log(f"bid_document {bidder_id}/{package.package_id}: done")
    return local_state.agent_discussion_history, bid


def _require_bid_response(data: dict) -> None:
    # Validate inside ask_json_async so its bounded, audited retry can request a
    # correction. Never absorb a discrepancy into an arbitrary cost bucket.
    require_bid_document_shape(data)


def _is_non_lead_consortium_member(state: SimulationState, company_id: str, package_id: str) -> bool:
    return any(item.package_id == package_id and company_id in item.member_company_ids and company_id != item.lead_company_id for item in state.consortiums)


def _lead_consortium(state: SimulationState, company_id: str, package_id: str):
    return next((item for item in state.consortiums if item.package_id == package_id and item.lead_company_id == company_id), None)


def _bid_prompt(
    state: SimulationState,
    bidder_id: str,
    bidder_name: str,
    bidder_type: str,
    package_id: str,
    bid_messages: list[DiscussionMessage] | None = None,
) -> str:
    package = package_by_id(state, package_id)
    consortium = next((item for item in state.consortiums if item.consortium_id == bidder_id), None)
    companies = [company_by_id(state, item) for item in consortium.member_company_ids] if consortium else [company_by_id(state, bidder_id)]
    own_company_ids = {company.company_id for company in companies}
    own_context = bidder_context(consortium, companies)
    decisions = bid_decisions(state, package_id, own_company_ids, bidder_type)
    competitors = competition_context(state, package_id, bidder_id, own_company_ids)
    discussion_stages = {"bid_participation_decision", "consortium_failure_reconsideration", "bid_document_generation"} if bidder_type == "company" else {
        "bid_participation_decision",
        "consortium_formation",
        "consortium_failure_reconsideration",
        "bid_document_generation",
    }
    discussion_messages = [
        msg
        for msg in state.agent_discussion_history
        if msg.company_id in {company.company_id for company in companies}
        and msg.package_id == package_id
        and msg.stage in discussion_stages
    ]
    # Isolated tasks can have the same local ids as old checkpoint messages.
    seen = {id(msg) for msg in discussion_messages}
    discussion_messages.extend(msg for msg in bid_messages or [] if id(msg) not in seen)
    discussions = [public_discussion_line(msg) for msg in discussion_messages]
    return (
        f"Bidder id: {bidder_id}\nBidder name: {bidder_name}\nBidder type: {bidder_type}\n"
        f"Package id: {package.package_id}\nPackage name: {package.package_name}\n"
        f"Scope: {package.scope}\nRequired role: {package.required_company_role}\n"
        f"Package capability needs: {package.qualification_requirements}\n"
        f"Owner bid content asks: {package.proposal_requirements}\n"
        f"Pricing asks: {package.pricing_requirements}\n"
        f"Bidder context:\n{own_context}\n"
        f"Visible competing bidder profiles for commercial positioning:\n{competitors}\n"
        f"Participation decisions:\n" + "\n".join(f"- {item}" for item in decisions) + "\n"
        f"Relevant internal discussion:\n" + "\n".join(f"- {item}" for item in discussions[-8:])
    )
