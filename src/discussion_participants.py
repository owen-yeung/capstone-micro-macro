from __future__ import annotations

from src.models import MemberAgent
from src.state_ops import final_agent


def round_participants(
    agents: list[MemberAgent],
    profile: str,
    is_summary_round: bool,
    *,
    single_agent_firm: bool = False,
) -> list[MemberAgent]:
    # A1: firm reduced to its final decision agent.
    if single_agent_firm:
        return [final_agent(agents)]
    if profile != "smoke":
        return [final_agent(agents)] if is_summary_round else agents
    final = final_agent(agents)
    non_final = next((agent for agent in agents if agent.agent_id != final.agent_id), None)
    return [agent for agent in [non_final, final] if agent]
