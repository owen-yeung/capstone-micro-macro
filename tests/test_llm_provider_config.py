import pytest

from src.llm_client import OpenAICompatibleClient
from src.llm_providers import LLMConfig, PROVIDER_SPECS, resolve_provider_config


def test_qwen_provider_defaults(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-dashscope-key")
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_MODEL", raising=False)
    monkeypatch.delenv("QWEN_BASE_URL", raising=False)
    cfg = resolve_provider_config("qwen")
    assert cfg.provider == "qwen"
    assert cfg.model == "qwen3.5-flash"
    assert cfg.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert cfg.api_key == "test-dashscope-key"


def test_qwen_api_key_alias(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setenv("QWEN_API_KEY", "alias-key")
    cfg = resolve_provider_config("qwen", model="qwen3.5-flash")
    assert cfg.api_key == "alias-key"
    assert cfg.model == "qwen3.5-flash"


def test_missing_qwen_key_raises(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DASHSCOPE_API_KEY"):
        resolve_provider_config("qwen")


def test_qwen_disables_thinking_in_invoke_kwargs():
    client = OpenAICompatibleClient.__new__(OpenAICompatibleClient)
    client.config = LLMConfig(
        provider="qwen",
        model="qwen3.5-flash",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="x",
    )
    kwargs = OpenAICompatibleClient._invoke_kwargs(client, 0.2)
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["extra_body"] == {"enable_thinking": False}


def test_groq_provider_defaults(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.delenv("GROQ_BASE_URL", raising=False)
    cfg = resolve_provider_config("groq")
    assert cfg.provider == "groq"
    assert cfg.model == "llama-3.1-8b-instant"
    assert cfg.base_url == "https://api.groq.com/openai/v1"
    assert cfg.api_key == "test-groq-key"


def test_provider_specs_include_qwen_compare_pair():
    assert "deepseek" in PROVIDER_SPECS
    assert "qwen" in PROVIDER_SPECS
    assert PROVIDER_SPECS["qwen"]["default_model"] == "qwen3.5-flash"
