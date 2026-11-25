# OrgBid paper ↔ this repository

Maps ARIN7600 (OrgBid) components onto `src/`, `scripts/`, and frozen Experiment 1 artifacts. Discrepancies are flags, not licenses to rewrite history.

Related: [implementation spec](baseline_comparison_implementation_spec.md), [paper drop-in](../paper/external_comparison_experiments.md).

## 1. Tendering protocol (paper Table 2 / twelve stages)

| Paper stage | Graph node in `src/workflow.py` | Stage module | Notes |
|---|---|---|---|
| Project | `project` | `src/stages/project_setup.py` | Frozen Experiment 1 loads `ProjectIdea` from case sources instead of generating it |
| Firms | `companies` | `generate_companies` | Experiment 1 uses `load_case_inputs` + two firms per bidding role |
| Rosters | `rosters` | `src/stages/rosters.py` | Shared once per case (`shared_rosters.json`) |
| Owner requirements / packages | `owner_requirements` | `src/stages/owner_requirements.py` | Experiment 1 “owner” stage |
| Participation (bid / no-bid / joint-bid intent) | `participation` | `src/stages/participation.py` | `ParticipationDecision.decision ∈ {bid, no_bid, bid_with_consortium}` |
| Joint-bid formation | `consortiums` | `src/stages/consortiums.py` + `src/group_discussion.py` | Intra-firm rounds 1–3 then inter-firm 4–5 then lead JSON |
| Reconsideration | `reconsideration` | `src/stages/reconsideration.py` | Licensed revision: solo bid or withdrawal after a failed joint bid |
| Bid documents | `bid_documents` | `src/stages/bid_documents.py` | Three internal rounds; who may submit is gated |
| Opening | `opening` | `src/stages/opening.py` | Currently opens all submitted bids; discussion is observational |
| Evaluation | `evaluation` | `src/stages/evaluation.py` | Owner discussion then `EvaluationReport` |
| Award | `award` | `src/stages/award.py` | Decision-holding member; `AwardResult` |
| Contract / handoff | `execution_placeholder` | `src/stages/execution_handoff.py` | **Discrepancy:** placeholder / GBA handoff, not the paper’s three-draft signing |

Experiment 1’s runner (`scripts/micro_org_experiment.py`) collapses the graph into three scored stages (`owner`, `bidders`, `award`) while still calling the same stage functions in order inside `bidders` and `award`.

## 2. Organizational firm

| Paper | Code |
|---|---|
| Role-specialized members | `MemberAgent` in `src/models.py`; roster from `generate_member_agents` |
| Decision-holding member | `final_agent()` in `src/state_ops.py` (`decision_authority == "final"`, else last member) |
| Intra-firm discussion | `AgentRuntime.discuss_async` |
| `multi` / `single` / `solo` | `AgentRuntime.organization_mode` (`CAPSTONE_ORGANIZATION_MODE`) |
| D3 / S4 / G3 (Experiment 2) | Action-host path `src/actions/organization_strategy.py`; G3 is **not** in frozen `src/` tender results |
| Single external voice | `require_management_decision`; only `final_agent` writes `ParticipationDecision` |
| Visibility / memory | `src/discussion_context.py`, `src/stage_memory.py` (last messages, not named last6/mem5/floor last8) |

## 3. Invariants I1–I6 and λ

The paper names I1–I6 and a typed λ ladder. The repository enforces pieces (prompt contracts, opening admissibility, hidden-benchmark comments, one JSON emit) but **does not** implement named I1–I6 checks or a typed λ object. Do not cite code identifiers I1–I6.

Hidden labels: `hidden_benchmark_project_enterprises.csv` (several copies under `data/` and `validation/`). Usage note in the CSV: not for simulation input.

## 4. Joint-bid emit

Paper: consortium exists as a product of member acceptances.  
Code: lead firm’s `ask_json` CONSORTIUM emit (`formed` / `not_formed`) after discussion. Acceptance product is not computed. Flag this if the paper is revised.

## 5. Experiment 1 artifacts used as prefixes

| Batch | Path | `multi` generation (requests / in / out tokens) |
|---|---|---|
| Six projects | `results/experiments/micro-org-1118/` | 1,749 / 11.09M / 1.18M |
| Three projects | `results/experiments/micro-org-replication-20261119/` | 798 / 4.76M / 0.51M |
| Three projects | `results/experiments/micro-org-extension12-20261119/` | 761 / 4.24M / 0.45M |
| **Twelve-project total** | | **3,308 / 20.09M / 2.13M** |

Judge model in those reports is `deepseek-flash` (the ARIN7600 text claims Qwen for judging; treat that as a paper/code discrepancy). Pair counts in the paper (217 multi–single) need not match a regenerated listing.

`full_run.zip` in each directory is Git LFS. Unpack via the baseline runner, not by treating the 133-byte pointer as a zip.

## 6. Rubric

Paper R1–R6 = `config/micro_org_rubric.json` (decision appropriateness, key-issue coverage, executability, risk and trade-off, evidence fidelity, internal consistency). Judge: `scripts/micro_org_judge.py`. Do not merge with CP07 D1–D4.

## 7. Highest discrepancies (do not silently “fix” in frozen results)

1. Stage 12 is `execution_placeholder`, not three-draft signing.
2. Consortium status is lead-LLM emit, not ∏ acceptances.
3. No named I1–I6 or typed λ in `src/`.
4. G3 missing from frozen tender-pipeline results.
5. Judge identity: reports on disk say `deepseek-flash`; paper text says Qwen.
6. Experiment 1 task/pair counts in the paper may not match a fresh walk of the zips; use the frozen `summary.json` units if they disagree.
