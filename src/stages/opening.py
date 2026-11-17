from __future__ import annotations

import asyncio

from src.agent_runtime import AgentRuntime
from src.models import OpeningRecord, SimulationState
from src.progress import log as progress_log
from src.stage_memory import owner_package_memory
from src.state_ops import company_by_role, log_event


async def open_bids(state: SimulationState, runtime: AgentRuntime) -> None:
    for package in state.tender_packages:
        bids = [bid for bid in state.bid_documents if bid.package_id == package.package_id]
        opened = [
            {
                "bid_id": bid.bid_id,
                "bidder_type": bid.bidder_type,
                "bidder_id": bid.bidder_id,
                "bidder_name": bid.bidder_name,
                "quotation": bid.quotation,
                "quotation_breakdown": bid.quotation_breakdown,
                "submission_summary": bid.submission_summary,
                "unresolved_condition_ids": list(bid.unresolved_condition_ids),
                "bid_assumptions": list(bid.bid_assumptions),
                "successfully_submitted": True,
            }
            for bid in bids
        ]
        state.opening_record.append(
            OpeningRecord(
                package.package_id,
                opened,
                f"{len(opened)} bids opened for {package.package_name}.",
                [],
            )
        )
        log_event(state, "opening_completed", {"package_id": package.package_id, "opened_bid_count": len(opened)})
    await _run_owner_opening_discussions(state, runtime)


async def _run_owner_opening_discussions(state: SimulationState, runtime: AgentRuntime) -> None:
    owner = company_by_role(state, "owner")[0]
    owner_agents = state.company_agent_rosters[owner.company_id]
    progress_log(f"opening: preparing {len(state.opening_record)} package observation discussions")
    raw_results = await asyncio.gather(
        *[_opening_discussion_task(state, runtime, record, owner, owner_agents) for record in state.opening_record],
        return_exceptions=True,
    )
    results = []
    for record, result in zip(state.opening_record, raw_results):
        if isinstance(result, Exception):
            runtime.record_recovery(
                "opening_discussion_skipped",
                package_id=record.package_id,
                error=f"{type(result).__name__}: {result}",
            )
            continue
        if isinstance(result, BaseException):
            raise result
        results.append(result)
    for index, messages in enumerate(results, start=1):
        runtime.import_messages(state, messages)
        progress_log(f"opening: recorded discussion {index}/{len(results)}")


async def _opening_discussion_task(state: SimulationState, runtime: AgentRuntime, record: OpeningRecord, owner, owner_agents) -> list:
    local_state = SimulationState()
    local_runtime = runtime.isolated_clone()
    await local_runtime.discuss_async(
        local_state,
        "bid_opening",
        owner,
        record.package_id,
        owner_agents,
        [(1, "submission_check"), (2, "evaluation_handoff_observation")],
        _opening_context(record),
        owner_package_memory(
            state,
            owner.company_id,
            record.package_id,
            disabled=runtime.ablation.no_cross_stage_memory,
        ),
    )
    return local_state.agent_discussion_history


def _opening_context(record: OpeningRecord) -> str:
    opened = "\n".join(
        f"- {item['bidder_id']} ({item['bidder_name']}), type={item['bidder_type']}, "
        f"quotation={item['quotation']}, submitted={item['successfully_submitted']}, "
        f"breakdown={item['quotation_breakdown']}, "
        f"unresolved_conditions={item.get('unresolved_condition_ids', [])}, assumptions={item.get('bid_assumptions', [])}, "
        f"summary={item['submission_summary']}"
        for item in record.opened_bids
    )
    return (
        f"Owner is recording the bid opening observations for {record.package_id}. "
        f"Opening is not an award decision; identify submission completeness, obvious clarification needs, "
        f"and what evaluators should pay attention to next. You may mention exact MOP quotations, "
        f"but do not compare bid prices with percentages, ratios, multipliers, or approximate expressions "
        f"such as percent gap, about half, twice, double, or times the lower bid.\n"
        f"Opening summary: {record.opening_summary}\n"
        f"Opened bids:\n{opened or 'No bids were opened.'}"
    )
