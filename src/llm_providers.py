"""Named OpenAI-compatible provider resolution (no SDK import)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LLMConfig:
    provider: str
    model: str
    base_url: str
    api_key: str
    timeout: int = 60


PROVIDER_SPECS: dict[str, dict[str, str]] = {
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "model_env": "DEEPSEEK_MODEL",
        "base_url_env": "DEEPSEEK_BASE_URL",
        "default_model": "deepseek-chat",
        "default_base_url": "https://api.deepseek.com/v1",
    },
    "groq": {
        "api_key_env": "GROQ_API_KEY",
        "model_env": "GROQ_MODEL",
        "base_url_env": "GROQ_BASE_URL",
        # Cheap default for provider-compare; override with llama-3.3-70b-versatile if needed.
        "default_model": "llama-3.1-8b-instant",
        "default_base_url": "https://api.groq.com/openai/v1",
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        "base_url_env": "OPENAI_BASE_URL",
        "default_model": "gpt-4o-mini",
        "default_base_url": "https://api.openai.com/v1",
    },
}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    return int(value) if value else default


def load_env_file(path: Path) -> bool:
    if not path.exists():
        return False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return True


def load_project_env() -> list[str]:
    root = Path(__file__).resolve().parents[1]
    paths = [Path.cwd() / ".env", root / ".env"]
    loaded: list[str] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if load_env_file(resolved):
            loaded.append(str(resolved))
    return loaded


def resolve_provider_config(
    provider: str | None = None,
    *,
    model: str | None = None,
) -> LLMConfig:
    """Resolve provider/model/base_url/api_key from env without constructing a client."""
    selected_provider = (provider or os.getenv("LLM_PROVIDER", "deepseek")).strip().lower()
    if not selected_provider:
        selected_provider = "deepseek"
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise ValueError("An explicit model override must be a nonempty name")
    selected_model = None if model is None else model.strip()

    if selected_provider in PROVIDER_SPECS:
        spec = PROVIDER_SPECS[selected_provider]
        api_key = os.getenv(spec["api_key_env"], "").strip()
        if not api_key:
            raise RuntimeError(
                f"{spec['api_key_env']} is required for LLM_PROVIDER={selected_provider}. "
                "Set it in .env or the shell environment."
            )
        return LLMConfig(
            provider=selected_provider,
            model=selected_model
            or os.getenv(spec["model_env"], spec["default_model"]).strip()
            or spec["default_model"],
            base_url=os.getenv(spec["base_url_env"], spec["default_base_url"]).strip()
            or spec["default_base_url"],
            api_key=api_key,
            timeout=env_int("LLM_TIMEOUT", 60),
        )

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required for generic OpenAI-compatible providers. "
            f"Unknown LLM_PROVIDER={selected_provider!r}; known: {sorted(PROVIDER_SPECS)}"
        )
    return LLMConfig(
        provider=selected_provider,
        model=selected_model or os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
        or "https://api.openai.com/v1",
        api_key=api_key,
        timeout=env_int("LLM_TIMEOUT", 60),
    )
