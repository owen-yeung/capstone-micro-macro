from __future__ import annotations

import asyncio
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from src.ablation import AblationConfig
from src.agent_runtime import AgentRuntime
from src.models import Company, ProjectIdea, SimulationState
from src.stages.award import make_award_decisions
from src.stages.bid_documents import generate_bid_documents
from src.stages.consortiums import form_consortiums
from src.stages.evaluation import evaluate_bids
from src.stages.execution_handoff import write_execution_handoff
from src.stages.opening import open_bids
from src.stages.owner_requirements import owner_refine_requirements
from src.stages.participation import run_bid_participation
from src.stages.project_setup import generate_companies, generate_project_idea
from src.stages.reconsideration import reconsider_after_failed_consortiums
from src.stages.rosters import generate_member_agents
from src.progress import elapsed, log as progress_log, timer
from src.state_ops import log_event
from src.run_audit import LLMCallAuditLogger
from src.workflow_checkpoint import END_STAGE, STAGE_ORDER, WorkflowCheckpointStore


class GraphState(TypedDict):
    sim: SimulationState
    project_prompt: str | None
    project_idea: ProjectIdea | None
    companies: list[Company] | None
    profile: str
    start_stage: str


class TenderSimulationWorkflow:
    def __init__(
        self,
        llm_client: Any,
        profile: str = "full",
        audit_logger: LLMCallAuditLogger | None = None,
        checkpoint_store: WorkflowCheckpointStore | None = None,
        ablation: AblationConfig | None = None,
    ):
        self.profile = profile
        self.ablation = ablation or AblationConfig.disabled()
        self.runtime = AgentRuntime(
            llm_client,
            profile=profile,
            audit_logger=audit_logger,
            ablation=self.ablation,
        )
        self.checkpoint_store = checkpoint_store
        self.graph = self._build_graph()

    def run(
        self,
        project_prompt: str | None = None,
        project_idea: ProjectIdea | None = None,
        companies: list[Company] | None = None,
    ) -> SimulationState:
        return asyncio.run(self.run_async(project_prompt, project_idea, companies))

    async def run_async(
        self,
        project_prompt: str | None = None,
        project_idea: ProjectIdea | None = None,
        companies: list[Company] | None = None,
    ) -> SimulationState:
        sim = SimulationState()
        start_stage = STAGE_ORDER[0]
        if self.checkpoint_store is not None and self.checkpoint_store.exists():
            sim, start_stage = self.checkpoint_store.load()
            self.runtime.restore_message_counter(sim)
            progress_log(f"checkpoint: restored, next stage={start_stage}")
        if start_stage == END_STAGE:
            self._attach_reliability(sim)
            return sim
        initial: GraphState = {
            "sim": sim,
            "project_prompt": project_prompt,
            "project_idea": project_idea,
            "companies": companies,
            "profile": self.profile,
            "start_stage": start_stage,
        }
        final = await self.graph.ainvoke(initial)
        self._attach_reliability(final["sim"])
        return final["sim"]

    def _build_graph(self):
        graph = StateGraph(GraphState)
        graph.add_node("resume", self._resume)
        graph.add_node("project", self._project)
        graph.add_node("companies", self._companies)
        graph.add_node("rosters", self._rosters)
        graph.add_node("owner_requirements", self._owner_requirements)
        graph.add_node("participation", self._participation)
        graph.add_node("consortiums", self._consortiums)
        graph.add_node("reconsideration", self._reconsideration)
        graph.add_node("bid_documents", self._bid_documents)
        graph.add_node("opening", self._opening)
        graph.add_node("evaluation", self._evaluation)
        graph.add_node("award", self._award)
        graph.add_node("execution_placeholder", self._execution_placeholder)
        graph.set_entry_point("resume")
        graph.add_conditional_edges(
            "resume",
            lambda state: state["start_stage"],
            {stage: stage for stage in STAGE_ORDER},
        )
        for start, end in [
            ("project", "companies"),
            ("companies", "rosters"),
            ("rosters", "owner_requirements"),
            ("owner_requirements", "participation"),
            ("participation", "consortiums"),
            ("consortiums", "reconsideration"),
            ("reconsideration", "bid_documents"),
            ("bid_documents", "opening"),
            ("opening", "evaluation"),
            ("evaluation", "award"),
            ("award", "execution_placeholder"),
            ("execution_placeholder", END),
        ]:
            graph.add_edge(start, end)
        return graph.compile()

    @staticmethod
    def _resume(state: GraphState) -> GraphState:
        return state

    def _attach_reliability(self, sim: SimulationState) -> None:
        sim.validation_context["reliability"] = self.runtime.reliability_summary()

    def _checkpoint(self, stage: str, sim: SimulationState) -> None:
        self._attach_reliability(sim)
        if self.checkpoint_store is not None:
            self.checkpoint_store.save(stage, sim)
            progress_log(f"checkpoint: saved after {stage}")

    async def _project(self, state: GraphState) -> GraphState:
        started = timer()
        progress_log("stage project: start")
        sim = state["sim"]
        if state.get("project_idea"):
            sim.project_idea = state["project_idea"]
        else:
            sim.project_idea = await generate_project_idea(self.runtime, state["project_prompt"])
        log_event(sim, "project_idea_generated", {"project_name": sim.project_idea.project_name})
        self._checkpoint("project", sim)
        progress_log(f"stage project: done ({elapsed(started)})")
        return state

    async def _companies(self, state: GraphState) -> GraphState:
        started = timer()
        progress_log("stage companies: start")
        sim = state["sim"]
        if state.get("companies"):
            sim.companies = state["companies"]
        else:
            sim.companies = await generate_companies(self.runtime, sim.project_idea, state["profile"])
        log_event(sim, "companies_generated", {"count": len(sim.companies)})
        self._checkpoint("companies", sim)
        progress_log(f"stage companies: done ({len(sim.companies)} companies, {elapsed(started)})")
        return state

    async def _rosters(self, state: GraphState) -> GraphState:
        started = timer()
        progress_log("stage rosters: start")
        sim = state["sim"]
        sim.company_agent_rosters = await generate_member_agents(sim.companies, self.runtime)
        log_event(sim, "company_agent_rosters_generated", {"company_count": len(sim.company_agent_rosters)})
        self._checkpoint("rosters", sim)
        progress_log(f"stage rosters: done ({elapsed(started)})")
        return state

    async def _owner_requirements(self, state: GraphState) -> GraphState:
        started = timer()
        progress_log("stage owner_requirements: start")
        sim = state["sim"]
        sim.owner_requirements = await owner_refine_requirements(sim, self.runtime, state["profile"])
        sim.tender_packages = sim.owner_requirements.tender_package_plan
        log_event(sim, "owner_requirements_published", {"package_count": len(sim.tender_packages)})
        self._checkpoint("owner_requirements", sim)
        progress_log(f"stage owner_requirements: done ({len(sim.tender_packages)} packages, {elapsed(started)})")
        return state

    async def _participation(self, state: GraphState) -> GraphState:
        started = timer()
        progress_log("stage participation: start")
        await run_bid_participation(state["sim"], self.runtime)
        self._checkpoint("participation", state["sim"])
        progress_log(f"stage participation: done ({elapsed(started)})")
        return state

    async def _consortiums(self, state: GraphState) -> GraphState:
        started = timer()
        progress_log("stage consortiums: start")
        await form_consortiums(state["sim"], self.runtime)
        self._checkpoint("consortiums", state["sim"])
        progress_log(f"stage consortiums: done ({len(state['sim'].consortiums)} consortiums, {elapsed(started)})")
        return state

    async def _reconsideration(self, state: GraphState) -> GraphState:
        started = timer()
        progress_log("stage reconsideration: start")
        await reconsider_after_failed_consortiums(state["sim"], self.runtime)
        self._checkpoint("reconsideration", state["sim"])
        progress_log(f"stage reconsideration: done ({elapsed(started)})")
        return state

    async def _bid_documents(self, state: GraphState) -> GraphState:
        started = timer()
        progress_log("stage bid_documents: start")
        await generate_bid_documents(state["sim"], self.runtime)
        self._checkpoint("bid_documents", state["sim"])
        progress_log(f"stage bid_documents: done ({len(state['sim'].bid_documents)} bids, {elapsed(started)})")
        return state

    async def _opening(self, state: GraphState) -> GraphState:
        started = timer()
        progress_log("stage opening: start")
        await open_bids(state["sim"], self.runtime)
        self._checkpoint("opening", state["sim"])
        progress_log(f"stage opening: done ({elapsed(started)})")
        return state

    async def _evaluation(self, state: GraphState) -> GraphState:
        started = timer()
        progress_log("stage evaluation: start")
        await evaluate_bids(state["sim"], self.runtime)
        self._checkpoint("evaluation", state["sim"])
        progress_log(f"stage evaluation: done ({elapsed(started)})")
        return state

    async def _award(self, state: GraphState) -> GraphState:
        started = timer()
        progress_log("stage award: start")
        await make_award_decisions(state["sim"], self.runtime)
        self._checkpoint("award", state["sim"])
        progress_log(f"stage award: done ({elapsed(started)})")
        return state

    def _execution_placeholder(self, state: GraphState) -> GraphState:
        started = timer()
        progress_log("stage execution_placeholder: start")
        sim = state["sim"]
        write_execution_handoff(sim)
        self._checkpoint("execution_placeholder", sim)
        progress_log(f"stage execution_placeholder: done ({elapsed(started)})")
        return state
