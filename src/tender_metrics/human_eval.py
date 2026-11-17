"""Human behavioral-plausibility rubric and agreement helpers (offline).

This supports interim §6.2's human evaluation + inter-rater agreement next step.
It does not fabricate ratings or claim expert/blind status for assistant fills.
"""

from __future__ import annotations

from collections import Counter
from math import sqrt
from typing import Any, Iterable, Sequence


RUBRIC_VERSION = "behavioral_plausibility_v1"

DIMENSIONS = (
    {
        "id": "BP1",
        "name": "Role-consistent reasoning",
        "scale": [0, 1, 2],
        "anchors": {
            "0": "Ignores role duties or invents authority the firm does not have",
            "1": "Partially role-aware with notable gaps",
            "2": "Consistently stays within stated role, package, and authority",
        },
    },
    {
        "id": "BP2",
        "name": "Evidence use",
        "scale": [0, 1, 2],
        "anchors": {
            "0": "No grounding in provided company/package facts",
            "1": "Uses some facts but also unsupported claims",
            "2": "Key claims cite available facts; unknowns left open",
        },
    },
    {
        "id": "BP3",
        "name": "Negotiation / deliberation plausibility",
        "scale": [0, 1, 2],
        "anchors": {
            "0": "Implausible leaps, contradictory positions, or rubber-stamp consensus",
            "1": "Mixed: some realistic exchange with unresolved contradictions",
            "2": "Trade-offs, objections, and settlement look organizationally credible",
        },
    },
    {
        "id": "BP4",
        "name": "Cross-stage consistency",
        "scale": [0, 1, 2],
        "anchors": {
            "0": "Later bids/positions contradict earlier participation without explanation",
            "1": "Mostly consistent with minor unexplained shifts",
            "2": "Participation → consortium/bid/award trail remains coherent",
        },
    },
    {
        "id": "BP5",
        "name": "Risk and commercial caution",
        "scale": [0, 1, 2],
        "anchors": {
            "0": "Ignores obvious commercial/risk constraints in the packet",
            "1": "Mentions risk but does not act on material constraints",
            "2": "Treats capacity, price, compliance, and uncertainty proportionately",
        },
    },
)


def blank_score_sheet(
    *,
    case_id: str,
    package_id: str,
    rater_id: str,
    artifact_paths: list[str],
) -> dict[str, Any]:
    return {
        "rubric_version": RUBRIC_VERSION,
        "case_id": case_id,
        "package_id": package_id,
        "rater_id": rater_id,
        "artifact_paths": artifact_paths,
        "scores": {dim["id"]: None for dim in DIMENSIONS},
        "rationales": {dim["id"]: "" for dim in DIMENSIONS},
        "overall_notes": "",
        "claims_forbidden": [
            "Not independent external expert validation until raters are independent humans.",
            "Not inter-rater reliability until >=2 human raters complete the same blinded packets.",
        ],
    }


def cohen_kappa(y1: Sequence[Any], y2: Sequence[Any]) -> float | None:
    """Unweighted Cohen's kappa for equal-length categorical ratings."""
    if len(y1) != len(y2) or not y1:
        return None
    n = len(y1)
    agree = sum(a == b for a, b in zip(y1, y2))
    p_o = agree / n
    c1 = Counter(y1)
    c2 = Counter(y2)
    labels = set(c1) | set(c2)
    p_e = sum((c1[label] / n) * (c2[label] / n) for label in labels)
    if abs(1.0 - p_e) < 1e-12:
        return 1.0 if abs(p_o - 1.0) < 1e-12 else 0.0
    return (p_o - p_e) / (1.0 - p_e)


def percent_agreement(y1: Sequence[Any], y2: Sequence[Any]) -> float | None:
    if len(y1) != len(y2) or not y1:
        return None
    return sum(a == b for a, b in zip(y1, y2)) / len(y1)


def summarize_rater_pair(
    sheets_a: Iterable[dict[str, Any]],
    sheets_b: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    by_key_a = {_sheet_key(sheet): sheet for sheet in sheets_a}
    by_key_b = {_sheet_key(sheet): sheet for sheet in sheets_b}
    shared = sorted(set(by_key_a) & set(by_key_b))
    per_dimension: dict[str, Any] = {}
    for dim in DIMENSIONS:
        dim_id = dim["id"]
        a_vals = []
        b_vals = []
        for key in shared:
            a = by_key_a[key]["scores"].get(dim_id)
            b = by_key_b[key]["scores"].get(dim_id)
            if a is None or b is None:
                continue
            a_vals.append(a)
            b_vals.append(b)
        per_dimension[dim_id] = {
            "n_pairs": len(a_vals),
            "percent_agreement": percent_agreement(a_vals, b_vals),
            "cohen_kappa": cohen_kappa(a_vals, b_vals),
        }
    return {
        "rubric_version": RUBRIC_VERSION,
        "shared_packets": len(shared),
        "per_dimension": per_dimension,
        "interpretation": (
            "Report kappa and percent agreement per dimension. Do not average into a single "
            "credibility score or claim expert validation from assistant-authored fills."
        ),
    }


def _sheet_key(sheet: dict[str, Any]) -> tuple[str, str]:
    return str(sheet.get("case_id")), str(sheet.get("package_id"))


def mean_sd(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {"n": 0, "mean": None, "sd": None}
    mean = sum(values) / len(values)
    if len(values) == 1:
        return {"n": 1, "mean": mean, "sd": 0.0}
    var = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return {"n": len(values), "mean": mean, "sd": sqrt(var)}
