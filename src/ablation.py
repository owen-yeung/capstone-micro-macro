"""Interim §5.5 / §6.2 ablation controls for the tendering workflow.

Each flag removes one mechanism while leaving other conditions unchanged:
- A1 single_agent_firm: each firm speaks only through its final decision agent
- A2 rule_consortium_no_negotiation: consortia form by deterministic pairing, no negotiation discussion
- A3 no_reconsideration: failed consortium seekers keep the failed decision (no second chance)
- A4 no_cross_stage_memory: later stages do not receive earlier discussion memory

These flags prepare offline-reproducible experiment arms. Enabling them for real
LLM runs still requires a fresh authorized task scope (see AGENTS.md).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


ABLATION_IDS = ("A1", "A2", "A3", "A4")


@dataclass(frozen=True)
class AblationConfig:
    single_agent_firm: bool = False  # A1
    rule_consortium_no_negotiation: bool = False  # A2
    no_reconsideration: bool = False  # A3
    no_cross_stage_memory: bool = False  # A4

    @classmethod
    def disabled(cls) -> "AblationConfig":
        return cls()

    @classmethod
    def from_id(cls, ablation_id: str) -> "AblationConfig":
        key = ablation_id.strip().upper()
        if key in {"", "NONE", "FULL", "BASE"}:
            return cls.disabled()
        mapping = {
            "A1": cls(single_agent_firm=True),
            "A2": cls(rule_consortium_no_negotiation=True),
            "A3": cls(no_reconsideration=True),
            "A4": cls(no_cross_stage_memory=True),
        }
        if key not in mapping:
            raise ValueError(f"Unknown ablation id {ablation_id!r}; expected one of {ABLATION_IDS} or none")
        return mapping[key]

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "AblationConfig":
        if not data:
            return cls.disabled()
        return cls(
            single_agent_firm=bool(data.get("single_agent_firm", False)),
            rule_consortium_no_negotiation=bool(data.get("rule_consortium_no_negotiation", False)),
            no_reconsideration=bool(data.get("no_reconsideration", False)),
            no_cross_stage_memory=bool(data.get("no_cross_stage_memory", False)),
        )

    def active_ids(self) -> list[str]:
        ids: list[str] = []
        if self.single_agent_firm:
            ids.append("A1")
        if self.rule_consortium_no_negotiation:
            ids.append("A2")
        if self.no_reconsideration:
            ids.append("A3")
        if self.no_cross_stage_memory:
            ids.append("A4")
        return ids

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["active_ids"] = self.active_ids()
        return payload
