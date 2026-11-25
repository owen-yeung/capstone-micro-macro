"""Shared contracts for stage-isolated baseline swaps.

Adapters consume frozen OrgBid artifacts and must write back the same dataclasses
the rest of the tendering protocol already scores: ParticipationDecision,
Consortium, BidDocument, EvaluationReport, AwardResult.
"""
from __future__ import annotations

from typing import Any, Iterable

HIDDEN_LABEL_MARKERS = (
    "hidden_benchmark",
    "matched_enterprise_name",
    "contract_amount",
    "actual_duration",
    "actual_start",
    "actual_finish",
    "visibility",
)


def assert_no_hidden_labels(payload: Any, *, path: str = "engine_input") -> None:
    """Refuse to send withheld historical outcomes into a comparison engine."""
    if isinstance(payload, dict):
        lowered = {str(key).lower() for key in payload}
        for marker in HIDDEN_LABEL_MARKERS:
            if marker in lowered or any(marker in str(key).lower() for key in payload):
                raise ValueError(f"Hidden historical field {marker!r} found in {path}")
        for key, value in payload.items():
            assert_no_hidden_labels(value, path=f"{path}.{key}")
        return
    if isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            assert_no_hidden_labels(value, path=f"{path}[{index}]")
        return
    if isinstance(payload, str):
        text = payload.lower()
        if "hidden_benchmark" in text or "此表为隐藏benchmark" in payload:
            raise ValueError(f"Hidden benchmark text leaked into {path}")


def opened_bidder_ids(opening_record: Iterable[Any], package_id: str) -> set[str]:
    for record in opening_record:
        if getattr(record, "package_id", None) != package_id:
            continue
        opened = getattr(record, "opened_bids", None) or []
        disqualified = {
            item.get("bidder_id")
            for item in (getattr(record, "disqualified_bids", None) or [])
            if isinstance(item, dict)
        }
        ids = {item.get("bidder_id") for item in opened if isinstance(item, dict)}
        ids.discard(None)
        return {str(item) for item in ids if item not in disqualified}
    return set()
