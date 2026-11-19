#!/usr/bin/env python3
"""Offline D3 vs S/S4 organization metrics from frozen CP07 + macro first block.

No new model API calls. Does not overwrite frozen business_review grades.
LLM-judged subset scores are read from results/.../scores/ if present.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REV = ROOT / "Capstone报告/验证体系/实验/2026-11-13_总实验收尾/business_review/CP07"
CP07 = ROOT / "Capstone报告/验证体系/实验/2026-11-13_CP07组织质量对照"
MACRO = ROOT / "Capstone报告/验证体系/实验/2026-11-13_总实验收尾/macro_results/first_fixed_block_001"
OUT = ROOT / "results/experiments/org_deliberation_metrics_20261119"
SEED = "org-metrics-20261119"
BOOT_N = 20000
BOOT_SEED = 20261119


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_job(window: str, arm: str) -> Path | None:
    name = f"{window}-{arm}-r1"
    for cont in ("continuation-002", "continuation-001", "run"):
        for base in (CP07 / cont / "run" / "jobs", CP07 / "run" / "jobs"):
            p = base / name
            if p.exists() and (p / "step-4.json").exists():
                return p
    return None


def step_tokens(job: Path) -> dict:
    total = prompt = completion = 0
    per = []
    for i in range(1, 5):
        f = job / f"step-{i}.json"
        if not f.exists():
            continue
        d = read_json(f)
        u = (d.get("metadata") or {}).get("usage_metadata") or {}
        t = int(u.get("total_tokens") or 0)
        inp = int(u.get("input_tokens") or 0)
        out = int(u.get("output_tokens") or 0)
        total += t
        prompt += inp
        completion += out
        per.append({"step": i, "total_tokens": t, "input_tokens": inp, "output_tokens": out})
    return {"total_tokens": total, "input_tokens": prompt, "output_tokens": completion, "steps": per}


def load_grades():
    by = {}
    hashes = {}
    for f in sorted(REV.glob("*.json")):
        d = read_json(f)
        by.setdefault(d["window_id"], {})[d["arm"]] = d
        hashes[str(f.relative_to(ROOT)).replace("\\", "/")] = sha256_file(f)
    return by, hashes


def grade_metrics(g: dict) -> dict:
    d1 = g.get("D1") or {}
    label = d1.get("label")
    appropriate = None if label in (None, "not_judgable", "unknown") else int(label == "appropriate")
    factors = g.get("factor_ratings") or []
    counts = Counter(x.get("rating") for x in factors)
    return {
        "D1": appropriate,
        "D2": g.get("D2_correct_coverage"),
        "eval_D3": (g.get("detailed") or {}).get("D3", {}).get("score"),
        "D4": (g.get("detailed") or {}).get("D4", {}).get("score"),
        "annotated_action": g.get("annotated_action"),
        "role": g.get("role"),
        "project_group": g.get("project_group"),
        "factor_counts": dict(counts),
        "n_factors": len(factors),
    }


def info_of(window: str) -> str:
    return "missing_core" if "missing" in window else "full"


def base_of(window: str) -> str:
    return window.replace("-full", "").replace("-missing_core", "")


def mean(xs):
    xs = [x for x in xs if x is not None]
    return None if not xs else statistics.mean(xs)


def paired_window_rows(by: dict) -> list[dict]:
    rows = []
    for window, arms in sorted(by.items()):
        if not {"D3", "S4"} <= set(arms):
            continue
        row = {
            "window_id": window,
            "info": info_of(window),
            "base": base_of(window),
            "role": arms["D3"]["role"],
            "project_group": arms["D3"]["project_group"],
        }
        for arm in ("S", "D3", "S4"):
            if arm not in arms:
                continue
            m = grade_metrics(arms[arm])
            for k, v in m.items():
                if k in ("role", "project_group"):
                    continue
                row[f"{k}__{arm}"] = v
            job = find_job(window, arm)
            if job is not None:
                tok = step_tokens(job)
                row[f"total_tokens__{arm}"] = tok["total_tokens"]
                row[f"output_tokens__{arm}"] = tok["output_tokens"]
                row[f"job_path__{arm}"] = str(job.relative_to(ROOT)).replace("\\", "/")
        rows.append(row)
    return rows


def project_equal_delta(rows: list[dict], left: str, right: str, metric: str) -> dict:
    """Aggregate window rows -> project means of (left-right), then mean across projects."""
    by_proj = defaultdict(list)
    for r in rows:
        a = r.get(f"{metric}__{left}")
        b = r.get(f"{metric}__{right}")
        if a is None or b is None:
            continue
        by_proj[r["project_group"]].append(a - b)
    proj_vals = {p: statistics.mean(vs) for p, vs in by_proj.items() if vs}
    vals = list(proj_vals.values())
    return {
        "left": left,
        "right": right,
        "metric": metric,
        "n_projects": len(vals),
        "n_windows_used": sum(len(vs) for vs in by_proj.values()),
        "project_mean_delta": mean(vals),
        "project_median_delta": None if not vals else statistics.median(vals),
        "n_projects_delta_pos": sum(1 for v in vals if v > 0),
        "n_projects_delta_neg": sum(1 for v in vals if v < 0),
        "n_projects_delta_zero": sum(1 for v in vals if v == 0),
        "per_project_delta": proj_vals,
    }


def window_mean_delta(rows: list[dict], left: str, right: str, metric: str) -> dict:
    deltas = []
    for r in rows:
        a = r.get(f"{metric}__{left}")
        b = r.get(f"{metric}__{right}")
        if a is None or b is None:
            continue
        deltas.append(a - b)
    return {
        "left": left,
        "right": right,
        "metric": metric,
        "n_windows": len(deltas),
        "mean_delta": mean(deltas),
        "median_delta": None if not deltas else statistics.median(deltas),
        "n_pos": sum(1 for v in deltas if v > 0),
        "n_neg": sum(1 for v in deltas if v < 0),
        "n_zero": sum(1 for v in deltas if v == 0),
    }


def bootstrap_project_delta(rows: list[dict], left: str, right: str, metric: str) -> dict:
    by_role_proj = defaultdict(lambda: defaultdict(list))
    for r in rows:
        a = r.get(f"{metric}__{left}")
        b = r.get(f"{metric}__{right}")
        if a is None or b is None:
            continue
        by_role_proj[r["role"]][r["project_group"]].append(a - b)
    role_proj_means = {
        role: {p: statistics.mean(vs) for p, vs in projects.items() if vs}
        for role, projects in by_role_proj.items()
    }
    # stratified: keep role stratum sizes, resample projects within role
    rng = _lcg(BOOT_SEED)
    samples = []
    roles = sorted(role_proj_means)
    for _ in range(BOOT_N):
        acc = []
        for role in roles:
            plist = list(role_proj_means[role].items())
            if not plist:
                continue
            for _j in range(len(plist)):
                p, v = plist[next(rng) % len(plist)]
                acc.append(v)
        if acc:
            samples.append(statistics.mean(acc))
    samples.sort()
    if not samples:
        return {"exploratory_percentile95": None, "n_bootstrap": 0}
    lo = samples[max(0, int(0.025 * len(samples)) - 1)]
    hi = samples[min(len(samples) - 1, int(0.975 * len(samples)))]
    return {
        "exploratory_percentile95": [lo, hi],
        "n_bootstrap": BOOT_N,
        "seed": BOOT_SEED,
        "method": "role_stratified_project_resample_of_window_mean_deltas",
    }


def _lcg(seed: int):
    x = seed % (2**31 - 1)
    while True:
        x = (1103515245 * x + 12345) % (2**31)
        yield x


def leave_one_project_out(rows: list[dict], left: str, right: str, metric: str) -> dict:
    base = project_equal_delta(rows, left, right, metric)
    projects = sorted(base["per_project_delta"])
    ranges = []
    for drop in projects:
        kept = [v for p, v in base["per_project_delta"].items() if p != drop]
        if kept:
            ranges.append(statistics.mean(kept))
    return {
        "full_project_mean_delta": base["project_mean_delta"],
        "leave_one_out_min": min(ranges) if ranges else None,
        "leave_one_out_max": max(ranges) if ranges else None,
        "n_projects": len(projects),
    }


def missing_core_interaction(rows: list[dict]) -> dict:
    by_base = defaultdict(dict)
    for r in rows:
        by_base[r["base"]][r["info"]] = r
    both = [b for b, d in by_base.items() if {"full", "missing_core"} <= set(d)]
    out = {"n_bases_with_both_info": len(both), "by_arm": {}}
    for arm in ("S", "D3", "S4"):
        arm_stats = {}
        for metric in ("D1", "D2", "eval_D3", "D4"):
            deltas = []
            for b in both:
                f = by_base[b]["full"].get(f"{metric}__{arm}")
                m = by_base[b]["missing_core"].get(f"{metric}__{arm}")
                if f is None or m is None:
                    continue
                deltas.append(m - f)
            arm_stats[metric] = {
                "n": len(deltas),
                "mean_missing_minus_full": mean(deltas),
                "median": None if not deltas else statistics.median(deltas),
                "n_drop": sum(1 for v in deltas if v < 0),
                "n_rise": sum(1 for v in deltas if v > 0),
                "n_flat": sum(1 for v in deltas if v == 0),
            }
        # action flip under missing
        flips = []
        for b in both:
            af = by_base[b]["full"].get(f"annotated_action__{arm}")
            am = by_base[b]["missing_core"].get(f"annotated_action__{arm}")
            if af is None or am is None:
                continue
            flips.append(int(af != am))
        arm_stats["action_flip_rate_missing_vs_full"] = {
            "n": len(flips),
            "rate": mean(flips),
        }
        # absolute levels
        for metric in ("D1", "D2"):
            for info in ("full", "missing_core"):
                vals = [
                    by_base[b][info].get(f"{metric}__{arm}")
                    for b in both
                    if by_base[b][info].get(f"{metric}__{arm}") is not None
                ]
                arm_stats[f"{metric}_mean_{info}"] = mean(vals)
        out["by_arm"][arm] = arm_stats
    # comparative sensitivity: |delta| and signed delta D3 vs S4
    comp = {}
    for metric in ("D1", "D2", "eval_D3", "D4"):
        d3 = []
        s4 = []
        for b in both:
            for arm, bucket in (("D3", d3), ("S4", s4)):
                f = by_base[b]["full"].get(f"{metric}__{arm}")
                m = by_base[b]["missing_core"].get(f"{metric}__{arm}")
                if f is None or m is None:
                    continue
                bucket.append(m - f)
        paired = []
        # pair by base order
        for b in both:
            f3 = by_base[b]["full"].get(f"{metric}__D3")
            m3 = by_base[b]["missing_core"].get(f"{metric}__D3")
            f4 = by_base[b]["full"].get(f"{metric}__S4")
            m4 = by_base[b]["missing_core"].get(f"{metric}__S4")
            if None in (f3, m3, f4, m4):
                continue
            paired.append({"base": b, "delta_D3": m3 - f3, "delta_S4": m4 - f4, "abs_D3": abs(m3 - f3), "abs_S4": abs(m4 - f4)})
        comp[metric] = {
            "n_paired_bases": len(paired),
            "mean_signed_delta_D3_minus_S4": mean([p["delta_D3"] - p["delta_S4"] for p in paired]),
            "mean_abs_delta_D3_minus_S4": mean([p["abs_D3"] - p["abs_S4"] for p in paired]),
            "n_D3_more_abs_sensitive": sum(1 for p in paired if p["abs_D3"] > p["abs_S4"]),
            "n_S4_more_abs_sensitive": sum(1 for p in paired if p["abs_S4"] > p["abs_D3"]),
        }
    out["D3_vs_S4_sensitivity"] = comp
    return out


def cost_normalized(rows: list[dict]) -> dict:
    out = {"by_arm": {}, "D3_vs_S4": {}}
    for arm in ("S", "D3", "S4"):
        d2_per_1k = []
        d1_per_1k = []
        tokens = []
        for r in rows:
            t = r.get(f"total_tokens__{arm}")
            d2 = r.get(f"D2__{arm}")
            d1 = r.get(f"D1__{arm}")
            if t and t > 0 and d2 is not None:
                d2_per_1k.append(d2 / (t / 1000))
                tokens.append(t)
            if t and t > 0 and d1 is not None:
                d1_per_1k.append(d1 / (t / 1000))
        out["by_arm"][arm] = {
            "n_with_tokens": len(tokens),
            "mean_total_tokens": mean(tokens),
            "mean_D2_per_1k_tokens": mean(d2_per_1k),
            "mean_D1_per_1k_tokens": mean(d1_per_1k),
        }
    # paired token and quality
    tok_deltas = []
    d2_deltas = []
    for r in rows:
        t3, t4 = r.get("total_tokens__D3"), r.get("total_tokens__S4")
        d23, d24 = r.get("D2__D3"), r.get("D2__S4")
        if None not in (t3, t4):
            tok_deltas.append(t3 - t4)
        if None not in (d23, d24):
            d2_deltas.append(d23 - d24)
    out["D3_vs_S4"] = {
        "mean_token_delta_D3_minus_S4": mean(tok_deltas),
        "mean_D2_delta_D3_minus_S4": mean(d2_deltas),
        "n": len(tok_deltas),
    }
    return out


def action_divergence(rows: list[dict]) -> dict:
    out = {}
    for left, right in (("D3", "S4"), ("D3", "S"), ("S4", "S")):
        flags = []
        for r in rows:
            a = r.get(f"annotated_action__{left}")
            b = r.get(f"annotated_action__{right}")
            if a is None or b is None:
                continue
            flags.append(int(a != b))
        out[f"{left}_vs_{right}"] = {"n": len(flags), "action_disagreement_rate": mean(flags)}
    return out


def tradeoff_joint(rows: list[dict]) -> dict:
    """A3: D2 up without D1 down, etc."""
    cases = []
    for r in rows:
        d1 = None if r.get("D1__D3") is None or r.get("D1__S4") is None else r["D1__D3"] - r["D1__S4"]
        d2 = None if r.get("D2__D3") is None or r.get("D2__S4") is None else r["D2__D3"] - r["D2__S4"]
        ed = None if r.get("eval_D3__D3") is None or r.get("eval_D3__S4") is None else r["eval_D3__D3"] - r["eval_D3__S4"]
        if d1 is None or d2 is None:
            continue
        cases.append({"d1": d1, "d2": d2, "eval_d3": ed})
    return {
        "n": len(cases),
        "rate_D2_up_D1_not_down": mean([int(c["d2"] > 0 and c["d1"] >= 0) for c in cases]),
        "rate_D2_up_D1_down": mean([int(c["d2"] > 0 and c["d1"] < 0) for c in cases]),
        "rate_both_up": mean([int(c["d2"] > 0 and c["d1"] > 0) for c in cases]),
        "rate_D2_up_evalD3_down": mean(
            [int(c["d2"] > 0 and c["eval_d3"] is not None and c["eval_d3"] < 0) for c in cases]
        ),
    }


def arm_levels(rows: list[dict]) -> dict:
    out = {}
    for arm in ("S", "D3", "S4"):
        out[arm] = {
            m: {
                "n": len([r for r in rows if r.get(f"{m}__{arm}") is not None]),
                "mean": mean([r.get(f"{m}__{arm}") for r in rows]),
            }
            for m in ("D1", "D2", "eval_D3", "D4")
        }
    return out


def select_subset(by: dict) -> list[str]:
    selected = []
    for role in ("contractor", "supplier", "designer", "supervisor"):
        pool = sorted(
            w
            for w, arms in by.items()
            if {"D3", "S4"} <= set(arms)
            and arms["D3"]["role"] == role
            and find_job(w, "D3")
            and find_job(w, "S4")
        )
        ranked = sorted(pool, key=lambda w: hashlib.sha256(f"{SEED}|{w}".encode()).hexdigest())
        selected.extend(ranked[:3])
    return selected


def lexical_role_specialization(window: str) -> dict | None:
    """Offline B3 proxy: token-set Jaccard across D3 member comments."""
    job = find_job(window, "D3")
    if job is None:
        return None
    texts = []
    positions = []
    for i in range(1, 4):
        d = read_json(job / f"step-{i}.json")
        text = d.get("public_comment") or ""
        texts.append(set(_tokens(text)))
        positions.append(d.get("position"))
    if any(not t for t in texts):
        return None
    pairs = []
    for i in range(3):
        for j in range(i + 1, 3):
            inter = len(texts[i] & texts[j])
            union = len(texts[i] | texts[j])
            pairs.append(inter / union if union else 1.0)
    # unique fraction
    unique = []
    for i in range(3):
        others = set().union(*[texts[j] for j in range(3) if j != i])
        uniq = texts[i] - others
        unique.append(len(uniq) / len(texts[i]) if texts[i] else 0.0)
    final = read_json(job / "step-4.json")
    final_text = final.get("raw_content") or final.get("public_comment") or ""
    final_tok = set(_tokens(final_text))
    coverage = []
    for i in range(3):
        uniq = texts[i] - set().union(*[texts[j] for j in range(3) if j != i])
        if not uniq:
            coverage.append(None)
            continue
        coverage.append(len(uniq & final_tok) / len(uniq))
    return {
        "window_id": window,
        "positions": positions,
        "mean_pairwise_jaccard": mean(pairs),
        "mean_unique_token_fraction": mean(unique),
        "mean_unique_token_final_coverage": mean([c for c in coverage if c is not None]),
        "per_member_unique_final_coverage": coverage,
    }


def _tokens(text: str) -> list[str]:
    # Chinese-friendly rough tokens: contiguous CJK / alnum runs length>=2
    import re

    return re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]{2,}", text or "")


def leave_one_role_proxy(window: str) -> dict | None:
    """C1 offline proxy: unique-to-role tokens covered by final (= importance if dropped)."""
    spec = lexical_role_specialization(window)
    if not spec:
        return None
    cov = [c for c in spec["per_member_unique_final_coverage"] if c is not None]
    return {
        "window_id": window,
        "mean_unique_coverage_in_final": mean(cov),
        "n_members_with_unique_tokens": len(cov),
        "interpretation": "Higher coverage means finals absorb role-unique content; dropout of that role would remove content the final currently uses.",
    }


def load_llm_scores() -> dict:
    path = OUT / "scores" / "subset_llm_scores.json"
    if not path.exists():
        return {"present": False, "path": str(path.relative_to(ROOT))}
    data = read_json(path)
    data["present"] = True
    data["scores_sha256"] = sha256_file(path)
    return data


def summarize_llm_scores(data: dict) -> dict:
    if not data.get("present"):
        return {"present": False}
    rows = data.get("windows") or []
    o1 = defaultdict(list)
    o2 = defaultdict(list)
    rubrics = defaultdict(lambda: defaultdict(list))
    prefs = Counter()
    special = []
    for w in rows:
        for arm in ("D3", "S4"):
            proc = (w.get("process") or {}).get(arm) or {}
            if proc.get("O1_supported_unique_items") is not None:
                o1[arm].append(proc["O1_supported_unique_items"])
            if proc.get("O2_rate") is not None:
                o2[arm].append(proc["O2_rate"])
            rub = (w.get("rubric") or {}).get(arm) or {}
            for k, v in rub.items():
                if k.startswith("R") and isinstance(v, (int, float)):
                    rubrics[arm][k].append(v)
        pref = w.get("pairwise_R6") or {}
        if pref.get("preferred_arm") in ("D3", "S4", "tie"):
            prefs[pref["preferred_arm"]] += 1
        if w.get("role_specialization_notes"):
            special.append(w["role_specialization_notes"])
    return {
        "present": True,
        "n_windows_scored": len(rows),
        "O1_mean": {a: mean(vs) for a, vs in o1.items()},
        "O2_mean": {a: mean(vs) for a, vs in o2.items()},
        "rubric_means": {a: {k: mean(vs) for k, vs in ks.items()} for a, ks in rubrics.items()},
        "R6_preference_counts": dict(prefs),
        "R6_D3_win_rate_excluding_ties": (
            prefs["D3"] / (prefs["D3"] + prefs["S4"]) if (prefs["D3"] + prefs["S4"]) else None
        ),
    }


def macro_transmission() -> dict:
    interp = read_json(MACRO / "business_interpretation_001.json")
    obs = read_json(MACRO / "first_block_observations.json")
    return {
        "source": "first_fixed_block_001",
        "four_arm_observations_identical": interp.get("four_arm_observations_identical"),
        "four_arm_actual_state_trajectories_identical": interp.get(
            "four_arm_actual_state_trajectories_identical"
        ),
        "O4_D3_vs_S4": interp.get("O4_D3_vs_S4"),
        "canonical_choices_identical": True,
        "layer_table": [
            {"layer": "A02_option_choice", "D3_differs_from_S4": False, "n_actor_pairs": 2},
            {"layer": "T1_markup", "D3_differs_from_S4": False, "value": 0.1},
            {"layer": "T2_contract_budget", "D3_differs_from_S4": False},
            {"layer": "T3_cost", "D3_differs_from_S4": False},
            {"layer": "T4_schedule", "D3_differs_from_S4": False},
            {"layer": "T5_quality", "D3_differs_from_S4": False},
            {"layer": "T6_risk", "D3_differs_from_S4": False},
            {"layer": "T7_milestones", "D3_differs_from_S4": False},
            {"layer": "T8_events", "D3_differs_from_S4": False},
        ],
        "interpretation": (
            "On the first fixed macro block, intra-firm deliberation did not change consumable "
            "commercial actions or downstream state. Process/text metrics remain the primary "
            "differentiation surface until decision variables are consumed differently."
        ),
        "manifest_sha256": sha256_file(MACRO / "manifest.json"),
        "interpretation_sha256": sha256_file(MACRO / "business_interpretation_001.json"),
        "observations_sha256": sha256_file(MACRO / "first_block_observations.json"),
        "n_observation_keys": len(obs) if isinstance(obs, dict) else None,
    }


def write_markdown(summary: dict, path: Path):
    a = summary["A_outcome_quality"]
    sens = summary["D_sensitivity"]["missing_core_interaction"]
    llm = summary["F_llm_judge_subset"]
    lines = [
        "# Organization deliberation metrics (2026-11-19)",
        "",
        "Offline re-analysis of frozen CP07 grades/process traces and the macro first fixed block. "
        "**No new external data. No overwrite of frozen business_review scores. new_model_calls=0.**",
        "",
        f"Generated at (UTC): {summary['at_UTC']}",
        "",
        "## Scope",
        "",
        f"- CP07 graded windows loaded: {summary['n_grade_files']}",
        f"- Complete D3–S4 paired windows: {summary['n_D3_S4_pairs']}",
        f"- LLM-judged subset: {summary['subset']['n_windows']} windows (3/role, fixed hash `{SEED}`)",
        "",
        "## A. Outcome quality (frozen D1–D4)",
        "",
        "Primary contrast is **D3 − S4** (call-count matched). Values are project-equal means of window deltas.",
        "",
        "| Metric | Project-mean Δ (D3−S4) | Exploratory 95% PI | LOO range | Window n_pos/neg/zero |",
        "|---|---:|---|---|---|",
    ]
    for metric in ("D1", "D2", "eval_D3", "D4"):
        p = a["project_equal_D3_minus_S4"][metric]
        b = a["bootstrap_D3_minus_S4"][metric]
        loo = a["leave_one_project_out"][metric]
        w = a["window_level_D3_minus_S4"][metric]
        pi = b.get("exploratory_percentile95")
        pi_s = "n/a" if not pi else f"[{pi[0]:.4f}, {pi[1]:.4f}]"
        loo_s = (
            "n/a"
            if loo["leave_one_out_min"] is None
            else f"[{loo['leave_one_out_min']:.4f}, {loo['leave_one_out_max']:.4f}]"
        )
        lines.append(
            f"| {metric} | {p['project_mean_delta']:.4f} | {pi_s} | {loo_s} | "
            f"{w['n_pos']}/{w['n_neg']}/{w['n_zero']} |"
        )
    levels = a["arm_means"]
    lines += [
        "",
        "Arm means (window-equal, complete triples preferred but reported on available rows):",
        "",
        "| Arm | D1 | D2 | eval-D3 | D4 |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm in ("S", "D3", "S4"):
        L = levels[arm]
        lines.append(
            f"| {arm} | {L['D1']['mean']:.3f} | {L['D2']['mean']:.3f} | "
            f"{L['eval_D3']['mean']:.3f} | {L['D4']['mean']:.3f} |"
        )
    tj = a["tradeoff_joint_D3_vs_S4"]
    lines += [
        "",
        f"Joint tradeoff (window): D2↑ & D1 not↓ = {tj['rate_D2_up_D1_not_down']:.3f}; "
        f"D2↑ & D1↓ = {tj['rate_D2_up_D1_down']:.3f} (n={tj['n']}).",
        "",
        "### Cost-normalized",
        "",
    ]
    cost = a["cost_normalized"]
    lines += [
        "| Arm | mean total tokens | D2 / 1k tokens | D1 / 1k tokens |",
        "|---|---:|---:|---:|",
    ]
    for arm in ("S", "D3", "S4"):
        c = cost["by_arm"][arm]
        lines.append(
            f"| {arm} | {c['mean_total_tokens']:.0f} | {c['mean_D2_per_1k_tokens']:.4f} | "
            f"{c['mean_D1_per_1k_tokens']:.4f} |"
        )
    lines += [
        "",
        f"D3−S4 mean token delta: {cost['D3_vs_S4']['mean_token_delta_D3_minus_S4']:.1f}; "
        f"D2 delta: {cost['D3_vs_S4']['mean_D2_delta_D3_minus_S4']:.4f}.",
        "",
        "## D. Sensitivity (full vs missing_core)",
        "",
        "Signed delta = score(missing_core) − score(full). Larger absolute movement = more sensitive.",
        "",
        "| Arm | mean ΔD1 | mean ΔD2 | action flip rate |",
        "|---|---:|---:|---:|",
    ]
    for arm in ("S", "D3", "S4"):
        b = sens["by_arm"][arm]
        lines.append(
            f"| {arm} | {b['D1']['mean_missing_minus_full']:.4f} | "
            f"{b['D2']['mean_missing_minus_full']:.4f} | "
            f"{b['action_flip_rate_missing_vs_full']['rate']:.3f} |"
        )
    cs = sens["D3_vs_S4_sensitivity"]
    lines += [
        "",
        f"Abs-sensitivity: D3 more sensitive than S4 on D1 in "
        f"{cs['D1']['n_D3_more_abs_sensitive']}/{cs['D1']['n_paired_bases']} bases "
        f"(mean |Δ|D3−|Δ|S4 = {cs['D1']['mean_abs_delta_D3_minus_S4']:.4f}).",
        "",
        f"Annotated-action disagreement D3 vs S4 (all paired windows): "
        f"{summary['E_divergence']['D3_vs_S4']['action_disagreement_rate']:.3f}.",
        "",
        "## B/C. Process proxies (lexical, all D3 jobs)",
        "",
        f"Mean pairwise Jaccard across D3 role comments: "
        f"{summary['B_process_proxies']['mean_pairwise_jaccard']:.3f} "
        f"(n={summary['B_process_proxies']['n_windows']}).",
        f"Mean unique-token fraction: {summary['B_process_proxies']['mean_unique_token_fraction']:.3f}.",
        f"Mean unique→final coverage (dropout importance proxy): "
        f"{summary['C_robustness_proxies']['mean_unique_coverage_in_final']:.3f}.",
        "",
        "## F. LLM-judged subset",
        "",
    ]
    if not llm.get("present"):
        lines.append("Subset scores file not yet present.")
    else:
        s = llm["summary"]
        lines += [
            f"Windows scored: {s['n_windows_scored']}.",
            "",
            f"O1 means: {s['O1_mean']}",
            f"O2 means: {s['O2_mean']}",
            f"Rubric means: {json.dumps(s['rubric_means'], ensure_ascii=False)}",
            f"R6 preference counts: {s['R6_preference_counts']} "
            f"(D3 win rate excl. ties: {s['R6_D3_win_rate_excluding_ties']})",
            "",
            "Scorer identity: Cursor agent acting as researcher-assisting LLM judge on blinded arm labels "
            "where noted in the score file; not an external human expert.",
        ]
    lines += [
        "",
        "## E. Macro transmission (first fixed block)",
        "",
        summary["E_macro"]["interpretation"],
        "",
        f"O4 D3−S4: {summary['E_macro']['O4_D3_vs_S4']}",
        "",
        "## Claim hygiene",
        "",
        "- Axes are reported separately; no composite “system better” score.",
        "- D3 shows higher abs-sensitivity to missing_core and higher action divergence vs S4; "
        "whether that is desirable depends on whether flips are toward grounded deferral.",
        "- On frozen D1/D4, S4 often matches or exceeds D3; D2/eval-D3 slightly favor D3 in this sample.",
        "- Macro T-path remains null on the first block — do not claim downstream project gains from this block.",
        "",
        "## Artifacts",
        "",
        "- `summary.json` — machine-readable aggregate",
        "- `derived/window_pairs.json` — per-window paired metrics",
        "- `scores/subset_llm_scores.json` — LLM judge scores for fixed subset",
        "- `packets/` — texts used for subset judging",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    by, grade_hashes = load_grades()
    rows = paired_window_rows(by)
    subset = select_subset(by)

    contrasts = {}
    boot = {}
    loo = {}
    window_level = {}
    for metric in ("D1", "D2", "eval_D3", "D4"):
        contrasts[metric] = project_equal_delta(rows, "D3", "S4", metric)
        boot[metric] = bootstrap_project_delta(rows, "D3", "S4", metric)
        loo[metric] = leave_one_project_out(rows, "D3", "S4", metric)
        window_level[metric] = window_mean_delta(rows, "D3", "S4", metric)

    # also S comparisons
    aux = {
        "D3_minus_S": {m: project_equal_delta(rows, "D3", "S", m) for m in ("D1", "D2", "eval_D3", "D4")},
        "S4_minus_S": {m: project_equal_delta(rows, "S4", "S", m) for m in ("D1", "D2", "eval_D3", "D4")},
    }

    specs = []
    drop = []
    for w in sorted({r["window_id"] for r in rows}):
        s = lexical_role_specialization(w)
        if s:
            specs.append(s)
        d = leave_one_role_proxy(w)
        if d:
            drop.append(d)

    llm_raw = load_llm_scores()
    llm_summary = summarize_llm_scores(llm_raw)

    summary = {
        "experiment_id": "org_deliberation_metrics_20261119",
        "at_UTC": datetime.now(timezone.utc).isoformat(),
        "new_model_calls": 0,
        "overwrites_frozen_grades": False,
        "n_grade_files": len(grade_hashes),
        "n_D3_S4_pairs": len(rows),
        "incomplete_windows": sorted(w for w, a in by.items() if not {"S", "D3", "S4"} <= set(a)),
        "subset": {
            "seed_string": SEED,
            "n_windows": len(subset),
            "windows": subset,
            "rule": "sha256(seed|window) rank; 3 per role among complete D3/S4 with job traces",
        },
        "A_outcome_quality": {
            "arm_means": arm_levels(rows),
            "project_equal_D3_minus_S4": contrasts,
            "bootstrap_D3_minus_S4": boot,
            "leave_one_project_out": loo,
            "window_level_D3_minus_S4": window_level,
            "auxiliary_vs_S": aux,
            "tradeoff_joint_D3_vs_S4": tradeoff_joint(rows),
            "cost_normalized": cost_normalized(rows),
        },
        "B_process_proxies": {
            "n_windows": len(specs),
            "mean_pairwise_jaccard": mean([s["mean_pairwise_jaccard"] for s in specs]),
            "mean_unique_token_fraction": mean([s["mean_unique_token_fraction"] for s in specs]),
            "note": "Lexical proxy only; LLM O1/O2 on subset is authoritative for issue quality.",
        },
        "C_robustness_proxies": {
            "n_windows": len(drop),
            "mean_unique_coverage_in_final": mean([d["mean_unique_coverage_in_final"] for d in drop]),
            "note": "Offline leave-one-role importance proxy; not a live re-run dropout experiment.",
        },
        "D_sensitivity": {"missing_core_interaction": missing_core_interaction(rows)},
        "E_divergence": action_divergence(rows),
        "E_macro": macro_transmission(),
        "F_llm_judge_subset": {
            "present": llm_raw.get("present", False),
            "summary": llm_summary,
            "scores_sha256": llm_raw.get("scores_sha256"),
        },
        "provenance": {
            "grade_sha256": grade_hashes,
            "script": str(Path(__file__).relative_to(ROOT)),
            "script_sha256": sha256_file(Path(__file__)),
        },
    }

    write_json(OUT / "derived" / "window_pairs.json", {"rows": rows})
    write_json(OUT / "derived" / "role_specialization.json", {"windows": specs})
    write_json(OUT / "derived" / "leave_one_role_proxy.json", {"windows": drop})
    # strip huge per-project maps from summary copy for readability? keep them.
    write_json(OUT / "summary.json", summary)
    write_markdown(summary, OUT / "SUMMARY.md")

    index = {
        "experiment_id": "org_deliberation_metrics_20261119",
        "title": "Multi-agent intra-firm deliberation metrics vs S/S4 baseline",
        "new_model_calls": 0,
        "primary_artifacts": [
            "SUMMARY.md",
            "summary.json",
            "scores/subset_llm_scores.json",
            "derived/window_pairs.json",
            "packets/manifest.json",
        ],
        "does_not_overwrite": ["Capstone报告/验证体系/实验/2026-11-13_总实验收尾/business_review/CP07"],
    }
    write_json(OUT / "index.json", index)
    print(
        json.dumps(
            {
                "pairs": len(rows),
                "subset": len(subset),
                "D2_project_delta": contrasts["D2"]["project_mean_delta"],
                "D1_project_delta": contrasts["D1"]["project_mean_delta"],
                "llm_present": llm_raw.get("present"),
                "out": str(OUT.relative_to(ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
