from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.llm_providers import (  # noqa: F401 - re-export for callers
    LLMConfig,
    PROVIDER_SPECS,
    env_int,
    load_env_file,
    load_project_env,
    resolve_provider_config,
)


@dataclass
class LLMResponse:
    content: str
    metadata: dict[str, Any]


class InvalidJSONResponseError(RuntimeError):
    """The provider returned content that could not be parsed as a JSON object."""


class OpenAICompatibleClient:
    def __init__(self, config: LLMConfig, env_files: list[str] | None = None):
        self.config = config
        self.env_files = env_files or []
        self._chat_model = ChatOpenAI(
            model=self.config.model,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            max_retries=0,
        )

    @classmethod
    def from_env(
        cls,
        *,
        provider: str | None = None,
        model: str | None = None,
    ) -> "OpenAICompatibleClient":
        """Load credentials and defaults, allowing explicit provider/model overrides."""
        env_files = load_project_env()
        return cls(resolve_provider_config(provider, model=model), env_files)

    def request_policy(self) -> dict[str, Any]:
        """Describe the actual no-retry transport without issuing a request."""
        import hashlib

        roots = (self._chat_model.root_client, self._chat_model.root_async_client)
        if (type(self._chat_model.max_retries) is not int or self._chat_model.max_retries != 0
                or any(root is None or type(root.max_retries) is not int or root.max_retries != 0 for root in roots)):
            raise RuntimeError("Bounded model calls require SDK retries to remain disabled")
        endpoint = self.config.base_url.rstrip("/")
        if (self._chat_model.model_name != self.config.model
                or any(str(root.base_url).rstrip("/") != endpoint for root in roots)):
            raise RuntimeError("Actual model transport differs from its explicit configuration")
        return {"schema_version": "model-request-policy.v1", "provider": self.config.provider,
                "model": self.config.model, "endpoint_sha256": hashlib.sha256(endpoint.encode()).hexdigest(),
                "internal_retries": 0, "max_requests_per_call": 1,
                "transport_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        return self.chat_with_metadata(messages, temperature).content

    async def achat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        return (await self.achat_with_metadata(messages, temperature)).content

    def chat_with_metadata(self, messages: list[dict[str, str]], temperature: float = 0.2) -> LLMResponse:
        return self._chat_sync(messages, temperature)

    async def achat_with_metadata(
        self, messages: list[dict[str, str]], temperature: float = 0.2
    ) -> LLMResponse:
        return await self._chat_async(messages, temperature)

    def _invoke_kwargs(self, temperature: float) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        if self.config.provider == "deepseek":
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        return kwargs

    @staticmethod
    def _lc_messages(messages: list[dict[str, str]]) -> list[SystemMessage | HumanMessage]:
        converted: list[SystemMessage | HumanMessage] = []
        for message in messages:
            if message["role"] == "system":
                converted.append(SystemMessage(content=message["content"]))
            else:
                converted.append(HumanMessage(content=message["content"]))
        return converted

    def _chat_sync(self, messages: list[dict[str, str]], temperature: float) -> LLMResponse:
        response = self._chat_model.invoke(self._lc_messages(messages), **self._invoke_kwargs(temperature))
        return self._response(response)

    async def _chat_async(self, messages: list[dict[str, str]], temperature: float) -> LLMResponse:
        response = await self._chat_model.ainvoke(self._lc_messages(messages), **self._invoke_kwargs(temperature))
        return self._response(response)

    @classmethod
    def _response(cls, response: Any) -> LLMResponse:
        metadata = {
            "id": getattr(response, "id", None),
            "response_metadata": getattr(response, "response_metadata", {}) or {},
            "usage_metadata": getattr(response, "usage_metadata", {}) or {},
        }
        return LLMResponse(cls._message_content(response), metadata)

    @staticmethod
    def _message_content(response: Any) -> str:
        content = response.content
        if isinstance(content, list):
            content = "".join(str(item) for item in content)
        if not content:
            raise RuntimeError(f"LLM response has empty content: {response}")
        return str(content)


def extract_json_object(text: str) -> dict[str, Any]:
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.strip("`")
        if clean.startswith("json"):
            clean = clean[4:].strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError as first_error:
        start = clean.find("{")
        end = clean.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise InvalidJSONResponseError(_json_error_message(first_error, clean)) from first_error
        try:
            return json.loads(clean[start : end + 1])
        except json.JSONDecodeError as second_error:
            raise InvalidJSONResponseError(_json_error_message(second_error, clean)) from second_error


def _json_error_message(error: json.JSONDecodeError, text: str) -> str:
    start = max(error.pos - 300, 0)
    end = min(error.pos + 300, len(text))
    snippet = text[start:end].replace("\n", "\\n")
    return f"LLM returned invalid JSON at char {error.pos}: {error.msg}. Snippet: {snippet}"
