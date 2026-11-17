from __future__ import annotations

import datetime as dt
import asyncio
import json
from typing import Any, Callable

from langchain_core.messages import HumanMessage, SystemMessage

from src.ablation import AblationConfig
from src.agent_message_contracts import require_agent_message
from src.discussion_participants import round_participants
from src.json_contract import with_json_contract
from src.llm_client import InvalidJSONResponseError, extract_json_object
from src.member_context import build_member_context
from src.message_import import import_discussion_messages
from src.models import Company, DiscussionMessage, MemberAgent, SimulationState
from src.prompt_loader import member_prompt
from src.progress import elapsed, log as progress_log, timer
from src.llm_throttle import LLMThrottle
from src.state_ops import final_agent
from src.run_audit import LLMCallAuditLogger
from src.response_recovery import normalize_agent_message


class AgentRuntime:
    JSON_PARSE_RETRIES = 1
    RESPONSE_CONTRACT_RETRIES = 1

    def __init__(
        self,
        llm_client: Any,
        profile: str = "full",
        audit_logger: LLMCallAuditLogger | None = None,
        company_grounding: bool = False,
        company_narrative_grounding: bool = False,
        task_role_grounding: bool = False,
        ablation: AblationConfig | None = None,
    ):
        self.llm = llm_client
        self.profile = profile
        self.ablation = ablation or AblationConfig.disabled()
        self.message_counter = 0
        self.throttle = LLMThrottle()
        self.audit_logger = audit_logger
        self.company_grounding = company_grounding
        if company_narrative_grounding and not company_grounding:
            raise ValueError('Narrative grounding requires company_grounding=True')
        self.company_narrative_grounding = company_narrative_grounding
        if task_role_grounding and not company_narrative_grounding:
            raise ValueError('Task role grounding requires company_narrative_grounding=True')
        self.task_role_grounding=task_role_grounding
        self.response_attempts: list[dict] = []
        self.recovery_events = audit_logger.recovery_events() if audit_logger is not None else []
        # Optional integration boundary. Offline workflows retain their old prompts.
        self.context_resolver = None
        self.context_entity_id = None

    def ask_json(self, system_prompt: str, marker: str, prompt: str) -> dict[str, Any]:
        return asyncio.run(self.ask_json_async(system_prompt, marker, prompt))

    def isolated_clone(self) -> "AgentRuntime":
        clone = AgentRuntime(self.llm, profile=self.profile, audit_logger=self.audit_logger,
                             company_grounding=self.company_grounding,
                             company_narrative_grounding=self.company_narrative_grounding,
                             task_role_grounding=self.task_role_grounding,
                             ablation=self.ablation)
        clone.throttle = self.throttle
        clone.recovery_events = self.recovery_events
        clone.response_attempts = self.response_attempts
        clone.message_counter = self.message_counter
        clone.context_resolver = self.context_resolver
        clone.context_entity_id = self.context_entity_id
        return clone

    def for_entity(self, entity_id: str) -> "AgentRuntime":
        if self.context_resolver is None:
            return self
        clone = self.isolated_clone()
        clone.context_entity_id = entity_id
        return clone

    def record_recovery(self, kind: str, **details: Any) -> dict[str, Any]:
        if self.audit_logger is not None:
            event = self.audit_logger.recovery(kind, **details)
        else:
            event = {"kind": kind, **details}
        self.recovery_events.append(event)
        return event

    def reliability_summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for event in self.recovery_events:
            kind = str(event.get("kind", "unknown"))
            counts[kind] = counts.get(kind, 0) + 1
        return {
            "status": "degraded" if self.recovery_events else "succeeded",
            "recovery_count": len(self.recovery_events),
            "recovery_counts": counts,
            "recovery_events_file": str(self.audit_logger.recovery_path) if self.audit_logger is not None else None,
        }

    def restore_message_counter(self, state: SimulationState) -> None:
        values = []
        for message in state.agent_discussion_history:
            try:
                values.append(int(message.message_id.rsplit("_", 1)[-1]))
            except (TypeError, ValueError):
                continue
        self.message_counter = max(values, default=0)

    async def ask_json_async(
        self,
        system_prompt: str,
        marker: str,
        prompt: str,
        validator: Callable[[dict[str, Any]], None] | None = None,
        normalizer: Callable[[dict[str, Any]], list[str]] | None = None,
    ) -> dict[str, Any]:
        started = timer()
        if self.context_resolver is not None:
            authorized = self.context_resolver(self.context_entity_id)
            currency = authorized["public"]["currency"]
            # Legacy tender prompts were Macau-specific. The task currency is
            # authoritative; no implicit FX conversion is performed.
            # Do not rewrite dynamic text: MOP may be part of a company ID.
            system_prompt += (f"\nFor this task, all proposed monetary amounts use {currency}. "
                              "This overrides generic currency examples in the template. "
                              "Preserve entity IDs and quoted input facts verbatim; do not convert currencies.")
            prompt += "\nAuthorized decision context:\n" + json.dumps(authorized, ensure_ascii=False)
        lc_messages = [
            SystemMessage(content=with_json_contract(system_prompt)),
            HumanMessage(content=f"{marker}\n{prompt}"),
        ]
        messages = [{"role": "system" if i == 0 else "user", "content": str(msg.content)} for i, msg in enumerate(lc_messages)]
        parse_retries = 0
        contract_retries = 0
        attempt_marker = marker
        attempt_messages = messages
        safe_mode = self.company_narrative_grounding and marker in {
            'MANAGEMENT_DECISION','RECONSIDER_AFTER_CONSORTIUM','BID_DOCUMENT'}
        repair_origin = None
        final_attempts = 0
        local_attempts = []
        while True:
            final_attempts += 1
            try:
                data, call_id, raw = await self._request_json_once(
                    attempt_marker,
                    attempt_messages,
                    started,
                    0.2 if attempt_marker == marker else 0.0,
                )
            except InvalidJSONResponseError as exc:
                if safe_mode:
                    raw = getattr(exc,'raw_content','')
                    parse_row={'marker':marker,'attempt':final_attempts,
                        'raw_content':raw,'status':'invalid_json','error':str(exc)}
                    self.response_attempts.append(parse_row)
                    local_attempts.append(parse_row)
                if hasattr(self.llm, "reject_response"):
                    self.llm.reject_response(attempt_messages, 0.2 if attempt_marker == marker else 0.0)
                if parse_retries >= self.JSON_PARSE_RETRIES or (safe_mode and final_attempts >= 2):
                    exc.output_attempts=local_attempts
                    raise
                parse_retries += 1
                self.record_recovery(
                    "json_parse_retry",
                    marker=marker,
                    retry=parse_retries,
                    error=f"{type(exc).__name__}: {exc}",
                )
                progress_log(f"llm {marker}: invalid JSON, retrying once with strict JSON instruction")
                attempt_marker = f"{marker}_JSON_RETRY"
                if safe_mode:
                    from src.response_repair import repair_messages
                    repair_origin=(raw,exc)
                    attempt_messages=repair_messages(messages,raw,exc)
                else:
                    attempt_messages = self._json_retry_messages(messages)
                continue
            row=None
            if safe_mode:
                from copy import deepcopy
                row={'marker':marker,'attempt':final_attempts,'call_id':call_id,
                     'raw_content':raw,'original_parsed':deepcopy(data),'status':'pending_validation'}
                self.response_attempts.append(row)
                local_attempts.append(row)
            if normalizer is not None and not safe_mode:
                changes = normalizer(data)
                if changes:
                    if self.audit_logger is not None:
                        self.audit_logger.normalized(call_id, marker, changes, data)
                    self.record_recovery("response_normalized", marker=marker, changes=changes, call_id=call_id)
            if validator is None:
                return data
            try:
                if safe_mode and repair_origin:
                    from src.response_repair import require_targeted_repair
                    row['repair_diff']=require_targeted_repair(repair_origin[0],data,repair_origin[1])
                validator(data)
            except (KeyError, TypeError, ValueError) as exc:
                if safe_mode:
                    from src.response_repair import issue_details
                    row.update(status='validation_failed',failure=issue_details(exc))
                    if hasattr(exc,'diff'):
                        row['repair_diff']=exc.diff
                if hasattr(self.llm, "reject_response"):
                    self.llm.reject_response(attempt_messages, 0.2 if attempt_marker == marker else 0.0)
                if self.audit_logger is not None:
                    self.audit_logger.contract_failed(call_id, exc)
                if (safe_mode and not getattr(exc,'retryable',True)) or contract_retries >= self.RESPONSE_CONTRACT_RETRIES or (safe_mode and final_attempts >= 2):
                    exc.output_attempts=local_attempts
                    raise
                contract_retries += 1
                self.record_recovery(
                    "response_contract_retry",
                    marker=marker,
                    retry=contract_retries,
                    error=f"{type(exc).__name__}: {exc}",
                    call_id=call_id,
                )
                progress_log(f"llm {marker}: response contract failed, retrying once: {exc}")
                attempt_marker = f"{marker}_SCHEMA_RETRY"
                if safe_mode:
                    from src.response_repair import repair_messages
                    repair_origin=(raw,exc)
                    attempt_messages=repair_messages(messages,raw,exc)
                else:
                    attempt_messages = self._schema_retry_messages(messages, exc)
                continue
            if self.audit_logger is not None:
                self.audit_logger.contract_validated(call_id)
            if row is not None:
                from copy import deepcopy
                row.update(status='limited_checks_passed',adopted=deepcopy(data))
            return data

    async def _request_json_once(
        self,
        marker: str,
        messages: list[dict[str, str]],
        started: float,
        temperature: float,
    ) -> tuple[dict[str, Any], str, str]:
        progress_log(f"llm {marker}: queued")
        async with self.throttle.semaphore:
            await self.throttle.wait_turn()
            request_started = timer()
            progress_log(f"llm {marker}: request")
            call_id = ""
            audit_started = request_started
            if self.audit_logger is not None:
                call_id, audit_started = self.audit_logger.begin(marker, messages, temperature)
            try:
                metadata: dict[str, Any] = {}
                if hasattr(self.llm, "achat_with_metadata"):
                    response = await self.llm.achat_with_metadata(messages, temperature=temperature)
                    content = response.content
                    metadata = response.metadata
                elif hasattr(self.llm, "achat"):
                    content = await self.llm.achat(messages, temperature=temperature)
                else:
                    content = await asyncio.to_thread(self.llm.chat, messages, temperature)
                if self.audit_logger is not None:
                    self.audit_logger.succeeded(call_id, audit_started, content, metadata)
            except BaseException as exc:
                if self.audit_logger is not None:
                    self.audit_logger.failed(call_id, audit_started, exc)
                raise
        progress_log(f"llm {marker}: response ({elapsed(request_started)} request, {elapsed(started)} total)")
        try:
            data = extract_json_object(content)
            if self.audit_logger is not None:
                self.audit_logger.parsed(call_id, data)
        except BaseException as exc:
            if self.audit_logger is not None:
                self.audit_logger.parse_failed(call_id, exc)
            if isinstance(exc,InvalidJSONResponseError):
                exc.raw_content=content
            raise
        progress_log(f"llm {marker}: parsed ({elapsed(started)} total)")
        return data, call_id, content

    @staticmethod
    def _json_retry_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
        return [
            *messages,
            {
                "role": "user",
                "content": (
                    "JSON_REPAIR_REQUIRED\n"
                    "Regenerate the answer to the original request as exactly one valid JSON object. "
                    "Return JSON only, without Markdown or commentary. Every string value, including "
                    "Chinese text, must be enclosed in double quotes. Do not omit required fields."
                ),
            },
        ]

    @staticmethod
    def _schema_retry_messages(messages: list[dict[str, str]], exc: BaseException) -> list[dict[str, str]]:
        return [
            *messages,
            {
                "role": "user",
                "content": (
                    "SCHEMA_REPAIR_REQUIRED\n"
                    f"The previous JSON failed validation: {exc}\n"
                    "Regenerate the complete answer to the original request as exactly one valid JSON object. "
                    "Include every required field and obey all field types and allowed values. Return JSON only."
                ),
            },
        ]

    def discuss(
        self,
        state: SimulationState,
        stage: str,
        company: Company,
        package_id: str,
        agents: list[MemberAgent],
        rounds: list[tuple[int, str]],
        context: str,
    ) -> None:
        asyncio.run(self.discuss_async(state, stage, company, package_id, agents, rounds, context))

    async def discuss_async(
        self,
        state: SimulationState,
        stage: str,
        company: Company,
        package_id: str,
        agents: list[MemberAgent],
        rounds: list[tuple[int, str]],
        context: str,
        memory_messages: list[DiscussionMessage] | None = None,
    ) -> None:
        previous: list[DiscussionMessage] = []
        memory_messages = memory_messages or []
        active_rounds = rounds[: min(2, len(rounds))] if self.profile == "smoke" else rounds
        for round_no, round_type in active_rounds:
            is_summary_round = round_no == active_rounds[-1][0]
            participants = round_participants(
                agents,
                self.profile,
                is_summary_round,
                single_agent_firm=self.ablation.single_agent_firm,
            )
            inputs = [(agent, previous[-6:], _agent_memory(memory_messages, agent)) for agent in participants]
            progress_log(
                f"discussion {stage}: round {round_no} {round_type}, "
                f"company={company.company_id}, package={package_id or '-'}, agents={len(inputs)}"
            )
            tasks = [self._ask_member(company, stage, round_type, package_id, context, item) for item in inputs]
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)
            results = []
            for item, result in zip(inputs, raw_results):
                if isinstance(result, Exception):
                    self.record_recovery(
                        "agent_call_isolated",
                        stage=stage,
                        company_id=company.company_id,
                        package_id=package_id or None,
                        agent_id=item[0].agent_id,
                        error=f"{type(result).__name__}: {result}",
                    )
                    progress_log(
                        f"discussion {stage}: isolated agent failure company={company.company_id}, "
                        f"agent={item[0].agent_id}: {type(result).__name__}: {result}"
                    )
                    continue
                if isinstance(result, BaseException):
                    raise result
                results.append(result)
            if not results:
                raise RuntimeError(
                    f"discussion {stage} failed because all {len(inputs)} agent calls failed; "
                    f"company={company.company_id}; package={package_id or '-'}"
                )
            for agent, prior_messages, data in results:
                msg = self.add_message(
                    state,
                    stage,
                    round_no,
                    round_type,
                    company,
                    package_id,
                    agent,
                    "opinion" if round_no < active_rounds[-1][0] else "summary",
                    data.get("thoughts", ""),
                    data["content"],
                    ["project_idea", "owner_requirements", "company_profile"],
                    [message.message_id for message in prior_messages],
                    data["recommendation"],
                    data["decision_impact"],
                    "",
                    verification_requests=data.get("verification_requests", []),
                )
                previous.append(msg)

    async def _ask_member(
        self,
        company: Company,
        stage: str,
        round_type: str,
        package_id: str,
        context: str,
        item: tuple[MemberAgent, list[DiscussionMessage], list[DiscussionMessage]],
    ) -> tuple[MemberAgent, list[DiscussionMessage], dict[str, Any]]:
        agent, prior_messages, memory_messages = item
        progress_log(f"member {stage}: asking {agent.agent_id}, package={package_id or '-'}, previous={len(prior_messages)}")
        try:
            data = await self.for_entity(company.company_id).ask_json_async(
                member_prompt(company.company_role),
                "AGENT_MESSAGE",
                build_member_context(stage, round_type, company, package_id, agent, context, prior_messages, memory_messages),
                validator=require_agent_message,
                normalizer=normalize_agent_message,
            )
        except (RuntimeError, KeyError, TypeError, ValueError) as exc:
            raise type(exc)(self._member_error_context(exc, stage, company, package_id, agent)) from exc
        progress_log(f"member {stage}: answered {agent.agent_id}, package={package_id or '-'}")
        return agent, prior_messages, data

    @staticmethod
    def _member_error_context(exc: Exception, stage: str, company: Company, package_id: str, agent: MemberAgent, keys: list[str] | None = None) -> str:
        suffix = f"; keys={keys}" if keys is not None else ""
        return f"{exc}; stage={stage}; company={company.company_id}; package={package_id or '-'}; agent={agent.agent_id}{suffix}"

    def add_message(
        self,
        state: SimulationState,
        stage: str,
        round_no: int,
        round_type: str,
        company: Company,
        package_id: str,
        agent: MemberAgent,
        message_type: str,
        thoughts: str,
        content: str,
        references: list[str],
        response_to: list[str],
        recommendation: str,
        decision_impact: str,
        final_decision: str,
        verification_requests: list[dict[str, Any]] | None = None,
    ) -> DiscussionMessage:
        self.message_counter += 1
        message = DiscussionMessage(
            f"msg_{self.message_counter:06d}",
            stage,
            round_no,
            round_type,
            company.company_id,
            company.company_role,
            package_id,
            agent.agent_id,
            agent.agent_name,
            agent.department,
            agent.position,
            message_type,
            thoughts,
            content,
            references,
            response_to,
            recommendation,
            decision_impact,
            final_decision,
            dt.datetime.now().isoformat(timespec="seconds"),
            verification_requests=list(verification_requests or []),
        )
        state.agent_discussion_history.append(message)
        return message

    def import_messages(self, state: SimulationState, messages: list[DiscussionMessage]) -> None:
        self.message_counter = import_discussion_messages(state, messages, self.message_counter)


def _agent_memory(messages: list[DiscussionMessage], agent: MemberAgent) -> list[DiscussionMessage]:
    direct = [message for message in messages if message.agent_id == agent.agent_id]
    if direct:
        return direct[-5:]
    same_company = [message for message in messages if message.company_id == agent.company_id]
    return same_company[-5:]
