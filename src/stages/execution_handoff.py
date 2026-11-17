from __future__ import annotations

from src.models import SimulationState
from src.state_ops import log_event

# Package role → native/GBA enterprise role labels used by construction-stage sources.
PACKAGE_TO_MACRO_ROLE = {
    "design_package": "designer",
    "contractor_package": "contractor",
    "supervision_package": "supervisor",
    "supplier_package": "supplier",
}


def write_execution_handoff(state: SimulationState) -> None:
    package_handoffs = [_package_handoff(state, award) for award in state.simulated_award_result.get("package_awards", [])]
    state.project_execution_log = {
        "status": "handoff_payload_ready_execution_not_run",
        "purpose": "Structured handoff from simulated tender award into a future project execution simulation.",
        "not_in_scope": [
            "construction progress simulation",
            "site events",
            "payment certification",
            "change orders",
            "delay analysis",
        ],
        "next_stage_inputs": [
            "simulated_award_result.json",
            "bid_documents.json",
            "evaluation_report.json",
            "opening_record.json",
            "agent_discussion_history.json",
        ],
        "macro_bridge": {
            "status": "mapping_only",
            "note": (
                "Maps award packages to native/GBA role labels. Does not start a construction "
                "lifecycle, invent payments, or claim macro execution evidence."
            ),
            "suggested_entrypoints": [
                "integration/native_lifecycle_actions.py",
                "vendor/gba/gba_construction_sim/",
            ],
            "required_before_execution": [
                "authorized construction-stage experiment scope",
                "synthetic financial/capacity assumptions declared as synthetic",
                "award unresolved clarifications closed or carried as pending conditions",
            ],
            "package_role_map": PACKAGE_TO_MACRO_ROLE,
            "awarded_entities": [
                {
                    "package_id": item["package_id"],
                    "macro_role": item["macro_role"],
                    "selected_bidder_id": item["selected_bidder_id"],
                    "bidder_type": item["bidder_type"],
                    "member_company_ids": item["member_company_ids"],
                    "quotation": item["quotation"],
                    "schedule_commitment": item["schedule_commitment"],
                    "pending_clarifications": item["pending_clarifications"],
                }
                for item in package_handoffs
            ],
        },
        "package_handoffs": package_handoffs,
    }
    log_event(
        state,
        "project_execution_handoff_written",
        {"package_count": len(package_handoffs), "macro_bridge": "mapping_only"},
    )


def _package_handoff(state: SimulationState, award: dict) -> dict:
    bid = next((item for item in state.bid_documents
                if item.bidder_id == award["selected_bidder_id"] and item.package_id == award["package_id"]), None)
    report = next((item for item in state.evaluation_report if item.package_id == award["package_id"]), None)
    member_ids = _member_company_ids(state, award)
    return {
        "package_id": award["package_id"],
        "macro_role": PACKAGE_TO_MACRO_ROLE.get(award["package_id"]),
        "selected_bidder_id": award["selected_bidder_id"],
        "selected_bidder_name": award["selected_bidder_name"],
        "bidder_type": award["bidder_type"],
        "member_company_ids": member_ids,
        "award_reason": award["decision_reason"],
        "quotation": bid.quotation if bid else None,
        "schedule_commitment": bid.schedule_commitment if bid else "",
        "risk_response": bid.risk_response if bid else "",
        "unresolved_condition_ids": list(award.get("unresolved_condition_ids", bid.unresolved_condition_ids if bid else [])),
        "pending_clarifications": list(award.get("pending_clarifications", [])),
        "bid_assumptions": list(bid.bid_assumptions) if bid else [],
        "evaluation_summary": report.comparison_summary if report else "",
        "owner_review_notes": report.owner_review_notes if report else "",
        "discussion_references": _discussion_references(state, award["package_id"]),
    }


def _member_company_ids(state: SimulationState, award: dict) -> list[str]:
    if award.get("bidder_type") == "company":
        return [str(award["selected_bidder_id"])]
    consortium = next(
        (item for item in state.consortiums if item.consortium_id == award.get("selected_bidder_id")),
        None,
    )
    if consortium is None:
        return []
    return list(consortium.member_company_ids)


def _discussion_references(state: SimulationState, package_id: str) -> list[str]:
    return [
        message.message_id
        for message in state.agent_discussion_history
        if message.package_id == package_id
        and message.stage in {"bid_opening", "evaluation", "owner_award_decision"}
    ][-8:]
