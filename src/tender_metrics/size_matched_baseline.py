"""Size-matched random baseline and package hit@1 for closed-pool tender awards.

Formula (interim §4.2 / Formula 6): with n role candidates, k observed reference
companies in that pool, and m firms selected by the simulation (consortium members
count individually),

    P_random = 1 - C(n - k, m) / C(n, m)

A package is scored only when at least one same-role reference company appears in
the closed candidate pool for that case. A hit occurs when any awarded firm matches
a reference company for the mapped role group.

Benchmark rows with a blank original role are assigned the sim role of that company
in the case candidate pool (reproduces the published 46/71 = 64.8% and 57.6% baseline).
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from math import comb
from pathlib import Path
from typing import Any, Iterable


PACKAGE_TO_SIM_ROLE = {
    "design_package": "designer",
    "contractor_package": "contractor",
    "supervision_package": "supervisor",
    "supplier_package": "supplier",
}

ROLE_GROUPS: dict[str, set[str]] = {
    "designer": {"设计", "勘察/测绘"},
    "contractor": {"施工/总承包", "专业分包"},
    "supervisor": {"监理", "咨询/顾问", "检测/质量控制", "造价/工料测量", "代建/项目管理"},
    "supplier": {"供应/制造"},
}

ORIGINAL_TO_SIM = {
    original: sim_role
    for sim_role, originals in ROLE_GROUPS.items()
    for original in originals
}


def size_matched_hit_probability(n: int, k: int, m: int) -> float:
    """Probability of drawing at least one of k references when choosing m of n."""
    if n <= 0 or m <= 0:
        raise ValueError("n and m must be positive")
    if m > n:
        raise ValueError("m cannot exceed n")
    if k < 0 or k > n:
        raise ValueError("k must be between 0 and n")
    if k == 0:
        return 0.0
    if n - k < m:
        return 1.0
    return 1.0 - comb(n - k, m) / comb(n, m)


def load_benchmark_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _case_id_from_dirname(name: str) -> str:
    # case-0001 -> CASE-0001
    prefix, _, number = name.partition("-")
    if prefix.lower() != "case" or not number:
        raise ValueError(f"Unexpected case directory name: {name}")
    return f"CASE-{number}"


def _award_members(case_dir: Path, award: dict[str, Any]) -> list[str]:
    if award.get("bidder_type") == "company":
        return [str(award["selected_bidder_id"])]
    consortiums = json.loads((case_dir / "consortiums.json").read_text(encoding="utf-8"))
    for item in consortiums:
        if item.get("consortium_id") == award.get("selected_bidder_id"):
            return [str(member_id) for member_id in item.get("member_company_ids", [])]
    raise ValueError(
        f"Consortium {award.get('selected_bidder_id')} missing in {case_dir / 'consortiums.json'}"
    )


def _refs_by_sim_role(
    case_id: str,
    benchmark_rows: Iterable[dict[str, str]],
    company_roles: dict[str, str],
) -> dict[str, set[str]]:
    refs: dict[str, set[str]] = defaultdict(set)
    for row in benchmark_rows:
        if row.get("case_id") != case_id:
            continue
        company_id = str(row.get("company_id") or "")
        if not company_id:
            continue
        original = (row.get("company_role_original") or "").strip()
        sim_role = ORIGINAL_TO_SIM.get(original)
        if sim_role is None:
            # Blank/unknown original roles: use the company's role in this case pool.
            candidate_role = company_roles.get(company_id)
            if candidate_role in ROLE_GROUPS:
                sim_role = candidate_role
            else:
                continue
        refs[sim_role].add(company_id)
    return refs


def score_case_packages(
    case_dir: Path,
    benchmark_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    case_id = _case_id_from_dirname(case_dir.name)
    companies = json.loads((case_dir / "companies.json").read_text(encoding="utf-8"))
    company_roles = {
        str(company["company_id"]): str(company["company_role"])
        for company in companies
        if company.get("company_role") != "owner"
    }
    refs_by_role = _refs_by_sim_role(case_id, benchmark_rows, company_roles)
    award_doc = json.loads((case_dir / "simulated_award_result.json").read_text(encoding="utf-8"))
    scored: list[dict[str, Any]] = []
    for award in award_doc.get("package_awards", []):
        package_id = str(award["package_id"])
        sim_role = PACKAGE_TO_SIM_ROLE[package_id]
        refs = refs_by_role.get(sim_role, set())
        if not refs:
            continue
        candidates = {company_id for company_id, role in company_roles.items() if role == sim_role}
        k = len(refs & candidates)
        if k == 0:
            continue
        members = _award_members(case_dir, award)
        member_set = list(dict.fromkeys(members))
        n = len(candidates)
        m = len(member_set)
        hit = any(member_id in refs for member_id in member_set)
        naive = (k / n) if n else None
        size_matched = size_matched_hit_probability(n, k, m)
        scored.append(
            {
                "case_id": case_id,
                "package_id": package_id,
                "sim_role": sim_role,
                "selected_bidder_id": award.get("selected_bidder_id"),
                "bidder_type": award.get("bidder_type"),
                "awarded_company_ids": member_set,
                "reference_company_ids": sorted(refs),
                "reference_in_pool_ids": sorted(refs & candidates),
                "candidate_company_ids": sorted(candidates),
                "n_candidates": n,
                "k_references_in_pool": k,
                "m_awarded": m,
                "hit": hit,
                "naive_single_draw_baseline": naive,
                "size_matched_baseline": size_matched,
            }
        )
    return scored


def score_archived_28_cases(
    cases_root: Path,
    benchmark_csv: Path,
) -> list[dict[str, Any]]:
    benchmark_rows = load_benchmark_rows(benchmark_csv)
    packages: list[dict[str, Any]] = []
    for case_dir in sorted(path for path in cases_root.iterdir() if path.is_dir()):
        packages.extend(score_case_packages(case_dir, benchmark_rows))
    return packages


def aggregate_package_scores(packages: list[dict[str, Any]]) -> dict[str, Any]:
    def _bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {
                "hits": 0,
                "denominator": 0,
                "hit_rate": None,
                "mean_size_matched_baseline": None,
                "mean_naive_single_draw_baseline": None,
                "margin_vs_size_matched": None,
            }
        hits = sum(1 for row in rows if row["hit"])
        denom = len(rows)
        mean_size = sum(row["size_matched_baseline"] for row in rows) / denom
        mean_naive = sum(row["naive_single_draw_baseline"] for row in rows) / denom
        hit_rate = hits / denom
        return {
            "hits": hits,
            "denominator": denom,
            "hit_rate": hit_rate,
            "mean_size_matched_baseline": mean_size,
            "mean_naive_single_draw_baseline": mean_naive,
            "margin_vs_size_matched": hit_rate - mean_size,
        }

    by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in packages:
        by_role[row["sim_role"]].append(row)

    case_hits: dict[str, bool] = defaultdict(bool)
    for row in packages:
        case_hits[row["case_id"]] = case_hits[row["case_id"]] or bool(row["hit"])

    return {
        "overall": _bucket(packages),
        "by_role": {role: _bucket(rows) for role, rows in sorted(by_role.items())},
        "case_any_hit": {
            "hits": sum(1 for value in case_hits.values() if value),
            "denominator": len(case_hits),
            "rate": (sum(1 for value in case_hits.values() if value) / len(case_hits)) if case_hits else None,
        },
        "reporting_rule": (
            "Always report package hit@1 with the size-matched baseline and role breakdown; "
            "do not publish overall hit rate alone under a closed candidate pool."
        ),
    }
