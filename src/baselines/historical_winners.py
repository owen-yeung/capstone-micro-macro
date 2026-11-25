"""Post-hoc historical winner column. Load only after ranking is finished."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HIDDEN = ROOT / "data/test_sources/casebank_enterprise_matched/hidden_benchmark_project_enterprises.csv"

ROLE_ALIASES = {
    "designer": {"设计", "研究"},
    "contractor": {"施工/总承包", "施工", "总承包"},
    "supplier": {"供应", "材料", "设备"},
    "supervisor": {"监理", "监察", "检测/质量控制", "代建/项目管理"},
}


def load_hidden_rows(path: Path | None = None) -> list[dict[str, str]]:
    source = path or DEFAULT_HIDDEN
    with source.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def historical_names(rows: list[dict[str, str]], case_id: str, role: str) -> list[str]:
    wanted = ROLE_ALIASES.get(role, {role})
    names = []
    for row in rows:
        if row.get("case_id") != case_id:
            continue
        original = (row.get("company_role_original") or "").strip()
        if original not in wanted:
            continue
        name = (row.get("matched_enterprise_name") or row.get("company_name") or "").strip()
        if name:
            names.append(name)
    return list(dict.fromkeys(names))


def annotate_winner_agreement(rows: list[dict], *, case_id: str, role_by_package: dict[str, str],
                              company_name_by_id: dict[str, str], hidden_path: Path | None = None) -> list[dict]:
    hidden = load_hidden_rows(hidden_path)
    annotated = []
    for row in rows:
        package_id = row["package_id"]
        role = role_by_package.get(package_id, "")
        historical = historical_names(hidden, case_id, role)
        org_name = company_name_by_id.get(row.get("orgbid_winner") or "", "")
        num_name = company_name_by_id.get(row.get("numerical_winner") or "", "")
        comparable = len(historical) == 1
        target = historical[0] if comparable else None
        annotated.append({
            **row,
            "historical_comparable": comparable,
            "historical_names": historical,
            "orgbid_matches_history": bool(comparable and org_name and org_name == target),
            "numerical_matches_history": bool(comparable and num_name and num_name == target),
        })
    return annotated


def package_roles(state) -> dict[str, str]:
    return {package.package_id: package.required_company_role for package in state.tender_packages}


def company_names(state) -> dict[str, str]:
    return {company.company_id: company.company_name for company in state.companies}


def index_hidden_by_case(path: Path | None = None) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in load_hidden_rows(path):
        grouped[row.get("case_id", "")].append(row)
    return dict(grouped)
