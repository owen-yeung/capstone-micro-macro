"""Offline tendering evaluation metrics (no model calls)."""

from src.tender_metrics.size_matched_baseline import (
    PACKAGE_TO_SIM_ROLE,
    ROLE_GROUPS,
    aggregate_package_scores,
    score_archived_28_cases,
    size_matched_hit_probability,
)

__all__ = [
    "PACKAGE_TO_SIM_ROLE",
    "ROLE_GROUPS",
    "aggregate_package_scores",
    "score_archived_28_cases",
    "size_matched_hit_probability",
]
