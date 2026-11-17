from __future__ import annotations

from src.models import DiscussionMessage, SimulationState


def company_package_memory(
    state: SimulationState,
    company_id: str,
    package_id: str,
    stages: set[str] | None = None,
    limit: int = 10,
    *,
    disabled: bool = False,
) -> list[DiscussionMessage]:
    # A4: cross-stage memory removed.
    if disabled:
        return []
    messages = [
        message
        for message in state.agent_discussion_history
        if message.company_id == company_id
        and message.package_id in {"", package_id}
        and (stages is None or message.stage in stages)
    ]
    return messages[-limit:]


def owner_package_memory(
    state: SimulationState,
    owner_id: str,
    package_id: str,
    limit: int = 10,
    *,
    disabled: bool = False,
) -> list[DiscussionMessage]:
    if disabled:
        return []
    return [
        message
        for message in state.agent_discussion_history
        if message.company_id == owner_id and message.package_id in {"", package_id}
    ][-limit:]
