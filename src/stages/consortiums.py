from __future__ import annotations

from src.agent_runtime import AgentRuntime
from src.discussion_context import public_discussion_line
from src.group_discussion import run_inter_company_discussion
from src.models import Company, Consortium, ParticipationDecision, SimulationState, TenderPackage
from src.progress import log as progress_log
from src.prompt_contracts import CONSORTIUM_FIELDS, require_consortium_shape, require_fields
from src.prompt_loader import load_prompt
from src.response_recovery import normalize_consortium
from src.stage_memory import company_package_memory
from src.state_ops import company_by_id, log_event, package_by_id
from src.verification import conditions, evidence_context


async def form_consortiums(state: SimulationState, runtime: AgentRuntime) -> None:
    requests = [item for item in state.participation_decisions if item.decision == "bid_with_consortium"]
    progress_log(f"consortiums: checking {len(requests)} consortium requests")
    for decision in state.participation_decisions:
        if decision.decision != "bid_with_consortium" or _already_in_consortium(state, decision.company_id, decision.package_id):
            continue
        lead = company_by_id(state, decision.company_id)
        package = package_by_id(state, decision.package_id)
        candidates = _candidate_partners(state, lead.company_id, package.package_id, package.required_company_role)
        progress_log(f"consortium {lead.company_id}/{package.package_id}: start with {len(candidates)} candidate partners")
        # A2: form consortia by deterministic rule without negotiation discussion.
        if runtime.ablation.rule_consortium_no_negotiation:
            _form_rule_consortium(state, lead, package, candidates)
            continue
        for company in [lead, *candidates]:
            progress_log(f"consortium {package.package_id}: discussion with {company.company_id}")
            try:
                await runtime.discuss_async(
                    state,
                    "consortium_formation",
                    company,
                    package.package_id,
                    state.company_agent_rosters[company.company_id],
                    [(1, "consortium_need_statement"), (2, "partner_response"), (3, "consortium_agreement")],
                    f"Companies consider a consortium for {package.package_name}.\nOwn documented profile:\n{_company_block(company)}\n"
                    + evidence_context(conditions(state, company.company_id, package.package_id)),
                    company_package_memory(
                        state,
                        company.company_id,
                        package.package_id,
                        {"bid_participation_decision"},
                        disabled=runtime.ablation.no_cross_stage_memory,
                    ),
                )
            except Exception as exc:
                runtime.record_recovery(
                    "consortium_discussion_skipped",
                    company_id=company.company_id,
                    package_id=package.package_id,
                    error=f"{type(exc).__name__}: {exc}",
                )
        if candidates:
            progress_log(f"consortium {lead.company_id}/{package.package_id}: inter-company negotiation")
            try:
                await run_inter_company_discussion(
                    state,
                    runtime,
                    "consortium_formation",
                    package.package_id,
                    [lead, *candidates],
                    [(4, "external_role_negotiation"), (5, "external_accountability_confirmation")],
                    _negotiation_context(state, lead, candidates, package),
                    _company_negotiation_contexts(state, [lead, *candidates], package.package_id),
                )
            except Exception as exc:
                runtime.record_recovery(
                    "consortium_negotiation_skipped",
                    company_id=lead.company_id,
                    package_id=package.package_id,
                    error=f"{type(exc).__name__}: {exc}",
                )
        try:
            data = await runtime.for_entity(lead.company_id).ask_json_async(
                load_prompt("company", "consortium.md"),
                "CONSORTIUM",
                _consortium_prompt(state, lead, candidates, package.package_id),
                validator=_require_consortium_response,
                normalizer=normalize_consortium,
            )
        except Exception as exc:
            runtime.record_recovery(
                "consortium_not_formed_fallback",
                company_id=lead.company_id,
                package_id=package.package_id,
                error=f"{type(exc).__name__}: {exc}",
            )
            log_event(state, "consortium_not_formed", {"company_id": lead.company_id, "package_id": package.package_id})
            continue
        if data["status"] != "formed":
            log_event(state, "consortium_not_formed", {"company_id": lead.company_id, "package_id": package.package_id})
            progress_log(f"consortium {lead.company_id}/{package.package_id}: not formed")
            continue
        member_ids = list(dict.fromkeys(data["member_company_ids"]))
        if lead.company_id not in member_ids or len(member_ids) < 2:
            raise ValueError(f"Invalid consortium members for {package.package_id}: {member_ids}")
        if not set(member_ids).issubset({lead.company_id, *(item.company_id for item in candidates)}):
            raise ValueError(f"Consortium contains unauthorized members for {package.package_id}")
        consortium = Consortium(
            f"consortium_{package.package_id}_{_next_consortium_no(state, package.package_id):03d}",
            data["consortium_name"],
            package.package_id,
            lead.company_id,
            member_ids,
            data["formation_reason"],
            data["role_split"],
            data["agreement_summary"],
            data["status"],
        )
        state.consortiums.append(consortium)
        log_event(state, "consortium_formed", {"consortium_id": consortium.consortium_id, "package_id": consortium.package_id})
        progress_log(f"consortium {consortium.consortium_id}: formed with {len(member_ids)} members")


def _form_rule_consortium(
    state: SimulationState,
    lead: Company,
    package: TenderPackage,
    candidates: list[Company],
) -> None:
    """A2 deterministic formation: lead + first unused willing partner, no negotiation."""
    partner = next((company for company in candidates if not _already_in_consortium(state, company.company_id, package.package_id)), None)
    if partner is None:
        log_event(
            state,
            "consortium_not_formed",
            {"company_id": lead.company_id, "package_id": package.package_id, "ablation": "A2", "reason": "no_partner"},
        )
        progress_log(f"consortium {lead.company_id}/{package.package_id}: A2 rule path not formed (no partner)")
        return
    member_ids = [lead.company_id, partner.company_id]
    consortium = Consortium(
        f"consortium_{package.package_id}_{_next_consortium_no(state, package.package_id):03d}",
        f"{lead.company_name}-{partner.company_name}联合体",
        package.package_id,
        lead.company_id,
        member_ids,
        "Ablation A2 rule formation without negotiation: first available willing partner paired with lead.",
        {
            lead.company_id: "Lead bidder; overall package accountability",
            partner.company_id: "Supporting partner under lead coordination",
        },
        "Rule-formed consortium for ablation A2; no negotiated role split.",
        "formed",
    )
    state.consortiums.append(consortium)
    log_event(
        state,
        "consortium_formed",
        {"consortium_id": consortium.consortium_id, "package_id": consortium.package_id, "ablation": "A2"},
    )
    progress_log(f"consortium {consortium.consortium_id}: A2 rule-formed with {len(member_ids)} members")


def _require_consortium_response(data: dict) -> None:
    require_fields(data, CONSORTIUM_FIELDS, "CONSORTIUM")
    require_consortium_shape(data)


def _candidate_partners(state: SimulationState, lead_id: str, package_id: str, role: str) -> list[Company]:
    unavailable = {
        member_id
        for item in state.consortiums
        if item.package_id == package_id
        for member_id in item.member_company_ids
    }
    ids = [
        item.company_id
        for item in state.participation_decisions
        if item.package_id == package_id
        and item.company_id != lead_id
        and item.company_id not in unavailable
        and item.decision in {"bid", "bid_with_consortium"}
    ]
    return [company_by_id(state, company_id) for company_id in ids]


def _already_in_consortium(state: SimulationState, company_id: str, package_id: str) -> bool:
    return any(item.package_id == package_id and company_id in item.member_company_ids for item in state.consortiums)


def _next_consortium_no(state: SimulationState, package_id: str) -> int:
    return len([item for item in state.consortiums if item.package_id == package_id]) + 1


def _consortium_prompt(state: SimulationState, lead: Company, candidates: list[Company], package_id: str) -> str:
    package = package_by_id(state, package_id)
    integration = state.validation_context.get("integration")
    decision_lines = "\n".join(
        (f"- {item.company_id}: available for authorized negotiation" if integration and item.company_id != lead.company_id else _decision_line(item))
        for item in state.participation_decisions if item.package_id == package_id)
    candidate_lines = "\n\n".join(_company_block(item) for item in candidates) or "No willing candidate partners."
    discussion = "\n".join(
        f"- {public_discussion_line(msg)}"
        for msg in state.agent_discussion_history
        if msg.package_id == package_id and msg.stage in {"bid_participation_decision", "consortium_formation"}
        and (not integration or msg.company_id == lead.company_id or msg.message_type == "negotiation")
    )
    return (
        f"Package:\n{_package_block(package)}\n\nLead company:\n{_company_block(lead)}\n\n"
        f"Package participation decisions:\n{decision_lines}\n\nCandidate partners:\n{candidate_lines}\n\n"
        f"Discussion:\n{discussion[-3500:]}"
    )


def _negotiation_context(state: SimulationState, lead: Company, candidates: list[Company], package: TenderPackage) -> str:
    partner_lines = "\n".join(f"- {company.company_id}: {company.company_name}" for company in candidates)
    return (
        f"Lead company {lead.company_id} is exploring a joint bid for {package.package_name}.\n"
        f"Potential partner companies:\n{partner_lines}\n"
        f"Only counterpart names are disclosed here. Do not infer specialisms, available staff, "
        f"or accepted commitments from a name. Ask counterparts for evidence and keep proposals conditional.\n"
        f"Package scope: {package.scope}\n"
        f"Package capability needs: {package.qualification_requirements}\n"
        f"Owner proposal asks: {package.proposal_requirements}\n"
        f"Discuss whether a joint bid is commercially acceptable, how responsibility would be split, "
        f"what each company needs before agreeing, and whether any company should still bid alone."
    )


def _company_negotiation_contexts(state: SimulationState, companies: list[Company], package_id: str) -> dict[str, str]:
    return {company.company_id: _company_negotiation_context(state, company.company_id, package_id) for company in companies}


def _company_negotiation_context(state: SimulationState, company_id: str, package_id: str) -> str:
    decision = _participation_decision(state, company_id, package_id)
    if not decision:
        return "No recorded participation decision. Explain your company's current position before negotiating."
    if decision.decision == "bid":
        stance = (
            "Your company previously chose to bid alone. Enter this negotiation as an independent bidder. "
            "Judge whether the proposed role is commercially better than the solo bid. If the role gives your company a distinct "
            "authority, fee share, risk control, or strategic advantage, you may explicitly abandon the solo bid and accept shared "
            "bidder accountability; otherwise keep the solo bid position."
        )
    elif decision.decision == "bid_with_consortium":
        stance = "Your company previously chose to seek a consortium. Explain what partner accountability would make the bid credible."
    else:
        stance = "Your company previously chose not to bid. Be cautious about re-entering unless the package position has materially changed."
    return (f"Recorded decision: {decision.decision}. Reason: {decision.reason}\n{stance}\n"
            + evidence_context(conditions(state, company_id, package_id)))


def _participation_decision(state: SimulationState, company_id: str, package_id: str) -> ParticipationDecision | None:
    return next((item for item in state.participation_decisions if item.company_id == company_id and item.package_id == package_id), None)


def _company_block(company: Company) -> str:
    return (
        f"- {company.company_id}: {company.company_name} ({company.company_role})\n"
        f"  profile: {company.profile}\n  strengths: {company.strengths}\n"
        f"  weaknesses: {company.weaknesses}\n  capabilities: {company.qualifications}\n"
        f"  capacity: {company.capacity}\n  risks: {company.risk_signals}"
    )


def _decision_line(decision: ParticipationDecision) -> str:
    return f"- {decision.company_id}: {decision.decision}; reason: {decision.reason}"


def _package_block(package: TenderPackage) -> str:
    return (
        f"{package.package_id}: {package.package_name}\nScope: {package.scope}\n"
        f"Required role: {package.required_company_role}\n"
        f"Package capability needs: {package.qualification_requirements}\n"
        f"Owner bid content asks: {package.proposal_requirements}"
    )
