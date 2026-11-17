import pytest

from src.llm_providers import PROVIDER_SPECS, resolve_provider_config


def test_groq_provider_defaults(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.delenv("GROQ_BASE_URL", raising=False)
    cfg = resolve_provider_config("groq")
    assert cfg.provider == "groq"
    assert cfg.model == "llama-3.1-8b-instant"
    assert cfg.base_url == "https://api.groq.com/openai/v1"
    assert cfg.api_key == "test-groq-key"


def test_groq_model_override(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    cfg = resolve_provider_config("groq", model="llama-3.3-70b-versatile")
    assert cfg.model == "llama-3.3-70b-versatile"


def test_missing_groq_key_raises(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        resolve_provider_config("groq")


def test_provider_specs_include_compare_pair():
    assert "deepseek" in PROVIDER_SPECS
    assert "groq" in PROVIDER_SPECS
