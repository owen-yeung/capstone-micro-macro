"""Numerical ranking of admissible opened bids (Experiment 4).

Replaces owner-side evaluation/award deliberation. Uses only attributes on the
opened record and the public firm profile. Historical winners are scored after
ranking, never as engine input.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np

from src.baselines.contracts import assert_no_hidden_labels, opened_bidder_ids
from src.models import AwardResult, BidDocument, Company, EvaluationReport, SimulationState, dump

CRITERIA = (
    ("quotation", -1),
    ("schedule_days", -1),
    ("declared_risk", -1),
    ("public_capability", 1),
)
DAY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:天|日|days?|day|weeks?|周|个月|months?|月)", re.I)


@dataclass(frozen=True)
class RankedBid:
    bidder_id: str
    bidder_name: str
    bidder_type: str
    closeness: float
    features: dict[str, float]


def _days(text: str) -> float | None:
    match = DAY_RE.search(text or "")
    if not match:
        return None
    value = float(match.group(1))
    token = match.group(0).lower()
    if "week" in token or "周" in token:
        return value * 7
    if "month" in token or "月" in token:
        return value * 30
    return value


def _capability(company: Company | None) -> float:
    if company is None:
        return 0.0
    return float(
        len(company.qualifications)
        + len(company.strengths)
        + len(company.past_project_experience)
    )


def _risk(bid: BidDocument, company: Company | None) -> float:
    signals = len(company.risk_signals) if company else 0
    return float(len(bid.unresolved_condition_ids) + signals)


def _company_map(state: SimulationState) -> dict[str, Company]:
    return {company.company_id: company for company in state.companies}


def admissible_bids(state: SimulationState, package_id: str) -> list[BidDocument]:
    bids = [bid for bid in state.bid_documents if bid.package_id == package_id]
    records = [record for record in state.opening_record if getattr(record, "package_id", None) == package_id]
    if not records:
        return bids
    opened = opened_bidder_ids(state.opening_record, package_id)
    return [bid for bid in bids if bid.bidder_id in opened]


def feature_row(bid: BidDocument, company: Company | None) -> dict[str, float | None]:
    return {
        "quotation": float(bid.quotation),
        "schedule_days": _days(bid.schedule_commitment),
        "declared_risk": _risk(bid, company),
        "public_capability": _capability(company),
    }


def _impute(columns: dict[str, list[float | None]]) -> dict[str, list[float]]:
    filled: dict[str, list[float]] = {}
    for name, values in columns.items():
        present = [value for value in values if value is not None and math.isfinite(value)]
        if not present:
            continue
        median = float(np.median(present))
        filled[name] = [float(value) if value is not None and math.isfinite(value) else median for value in values]
    return filled


def topsis_closeness(matrix: np.ndarray, weights: np.ndarray, benefit: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=0)
    norms = np.where(norms == 0, 1.0, norms)
    weighted = (matrix / norms) * weights
    ideal = np.where(benefit > 0, weighted.max(axis=0), weighted.min(axis=0))
    nadir = np.where(benefit > 0, weighted.min(axis=0), weighted.max(axis=0))
    d_ideal = np.linalg.norm(weighted - ideal, axis=1)
    d_nadir = np.linalg.norm(weighted - nadir, axis=1)
    denom = d_ideal + d_nadir
    denom = np.where(denom == 0, 1.0, denom)
    return d_nadir / denom


def entropy_weights(matrix: np.ndarray) -> np.ndarray:
    shifted = matrix - matrix.min(axis=0, keepdims=True) + 1e-12
    shares = shifted / shifted.sum(axis=0, keepdims=True)
    k = 1.0 / math.log(max(len(matrix), 2))
    entropy = -k * np.nansum(shares * np.log(shares), axis=0)
    diversity = 1.0 - entropy
    if float(diversity.sum()) == 0:
        return np.ones(matrix.shape[1]) / matrix.shape[1]
    return diversity / diversity.sum()


def rank_package(
    state: SimulationState,
    package_id: str,
    *,
    weight_mode: str = "equal",
) -> list[RankedBid]:
    companies = _company_map(state)
    bids = admissible_bids(state, package_id)
    payload = [dump(bid) for bid in bids]
    assert_no_hidden_labels({"package_id": package_id, "bids": payload})
    if not bids:
        return []
    rows = [feature_row(bid, companies.get(bid.bidder_id)) for bid in bids]
    columns = {name: [row[name] for row in rows] for name, _sign in CRITERIA}
    filled = _impute(columns)
    names = [name for name, _sign in CRITERIA if name in filled]
    if not names:
        names = ["quotation"]
        filled = {"quotation": [float(bid.quotation) for bid in bids]}
    matrix = np.column_stack([filled[name] for name in names])
    benefit = np.array([1.0 if dict(CRITERIA)[name] > 0 else 0.0 for name in names])
    if weight_mode == "entropy":
        weights = entropy_weights(matrix)
    else:
        weights = np.ones(len(names)) / len(names)
    closeness = topsis_closeness(matrix, weights, benefit)
    ranked = sorted(
        (
            RankedBid(
                bid.bidder_id,
                bid.bidder_name,
                bid.bidder_type,
                float(score),
                {name: filled[name][index] for name in names},
            )
            for index, (bid, score) in enumerate(zip(bids, closeness))
        ),
        key=lambda item: (-item.closeness, item.bidder_id),
    )
    return ranked


def weighted_sum_rank(state: SimulationState, package_id: str) -> list[RankedBid]:
    ranked = rank_package(state, package_id, weight_mode="equal")
    if not ranked:
        return []
    names = list(ranked[0].features)
    signs = {name: dict(CRITERIA).get(name, 1) for name in names}
    scored = []
    for item in ranked:
        total = 0.0
        for name in names:
            value = item.features[name]
            total += value * signs[name]
        scored.append(
            RankedBid(item.bidder_id, item.bidder_name, item.bidder_type, -total, item.features)
        )
    return sorted(scored, key=lambda item: (-item.closeness, item.bidder_id))


def evaluation_from_ranking(package_id: str, ranked: list[RankedBid]) -> EvaluationReport:
    if not ranked:
        return EvaluationReport(
            package_id,
            ["topsis"],
            [],
            "No admissible bids were opened; no award recommendation was made.",
            None,
            "Numerical ranking issued no winner because the opened set was empty.",
        )
    evaluations = [
        {
            "bidder_id": item.bidder_id,
            "closeness": item.closeness,
            "features": item.features,
            "rank": index,
        }
        for index, item in enumerate(ranked, start=1)
    ]
    winner = ranked[0]
    return EvaluationReport(
        package_id,
        ["topsis"],
        evaluations,
        "Closeness-to-ideal ranking of admissible opened bids on price, programme, declared risk, and public capability.",
        winner.bidder_id,
        f"Top-1 closeness {winner.closeness:.4f} for {winner.bidder_id}.",
    )


def award_from_ranking(package_id: str, ranked: list[RankedBid]) -> AwardResult:
    if not ranked:
        return AwardResult(package_id, None, "", "", "No admissible bids; no award.")
    winner = ranked[0]
    return AwardResult(
        package_id,
        winner.bidder_id,
        winner.bidder_name,
        winner.bidder_type,
        f"Numerical ranking selected {winner.bidder_id} (closeness {winner.closeness:.4f}).",
    )


def kendall_tau(order_a: list[str], order_b: list[str]) -> float | None:
    common = [item for item in order_a if item in set(order_b)]
    if len(common) < 2:
        return None
    rank_b = {item: index for index, item in enumerate(order_b)}
    concordant = discordant = 0
    for i, left in enumerate(common):
        for right in common[i + 1 :]:
            sign = (rank_b[right] - rank_b[left])
            if sign > 0:
                concordant += 1
            elif sign < 0:
                discordant += 1
    total = concordant + discordant
    if total == 0:
        return 1.0
    return (concordant - discordant) / total


def orgbid_rank(state: SimulationState, package_id: str) -> list[str]:
    for report in state.evaluation_report:
        if report.package_id != package_id:
            continue
        rows = []
        for index, item in enumerate(report.bid_evaluations or []):
            if not isinstance(item, dict):
                continue
            bidder = item.get("bidder_id") or item.get("company_id")
            if not bidder:
                continue
            rows.append((index, str(bidder)))
        if report.recommended_winner:
            rows.sort(key=lambda pair: (0 if pair[1] == report.recommended_winner else 1, pair[0]))
        order = list(dict.fromkeys(item for _index, item in rows))
        if report.recommended_winner and report.recommended_winner not in order:
            order.insert(0, report.recommended_winner)
        return order
    return []


def compare_package(state: SimulationState, package_id: str, *, weight_mode: str = "equal") -> dict:
    ranked = rank_package(state, package_id, weight_mode=weight_mode)
    org_order = orgbid_rank(state, package_id)
    num_order = [item.bidder_id for item in ranked]
    org_winner = next(
        (report.recommended_winner for report in state.evaluation_report if report.package_id == package_id),
        None,
    )
    num_winner = ranked[0].bidder_id if ranked else None
    return {
        "package_id": package_id,
        "weight_mode": weight_mode,
        "orgbid_winner": org_winner,
        "numerical_winner": num_winner,
        "winner_agreement": bool(org_winner) and org_winner == num_winner,
        "n_admissible": len(ranked),
        "kendall_tau": kendall_tau(org_order, num_order),
        "orgbid_order": org_order,
        "numerical_order": num_order,
        "evaluation_report": dump(evaluation_from_ranking(package_id, ranked)),
        "award_result": dump(award_from_ranking(package_id, ranked)),
    }


def compare_state(state: SimulationState, *, weight_mode: str = "equal") -> list[dict]:
    package_ids = [package.package_id for package in state.tender_packages] or list(
        dict.fromkeys(bid.package_id for bid in state.bid_documents)
    )
    return [compare_package(state, package_id, weight_mode=weight_mode) for package_id in package_ids]
