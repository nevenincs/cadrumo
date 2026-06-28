"""Unit tests for the public LLM client.

Exercises :class:`aeat.adapters.outbound.llm.LLMClient` against the
deterministic provider adapter to verify cache reuse, error surfacing, and
that secret material configured via :class:`aeat.core.config.Settings` never
leaks through ``repr`` or JSON serialization.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict

from .....core.config import LLMProviderSetting, Settings
from .. import (
    LLMCache,
    LLMClient,
    LLMProviderError,
    LLMRateLimitError,
    LLMRequest,
    UsageRecorder,
)
from .._providers import ProviderRequest, _DeterministicAdapter

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _IsolatedSettings(Settings):
    model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8")


def test_deterministic_adapter_contract() -> None:
    """The deterministic adapter should satisfy the provider contract."""

    adapter = _DeterministicAdapter(response_text="done")
    completion = asyncio.run(
        adapter.complete(
            ProviderRequest(
                request_id="req",
                model="claude-sonnet-4-6",
                prompt="hello",
                system=None,
                max_tokens=32,
                temperature=0.0,
                timeout_s=30,
            ),
        ),
    )
    assert completion.text == "done:hello"
    assert adapter.calls == 1


def test_client_uses_cache_before_calling_provider(tmp_path: Path) -> None:
    """A repeated request should hit the cache instead of re-calling the adapter."""

    settings = _IsolatedSettings(
        aeat_llm_provider=LLMProviderSetting.ANTHROPIC,
        aeat_llm_model="claude-sonnet-4-6",
        aeat_llm_cache_dir=tmp_path / "cache",
        aeat_llm_usage_dir=tmp_path / "usage",
    )
    adapter = _DeterministicAdapter(response_text="cached")
    client = LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=tmp_path / "cache"),
        usage_recorder=UsageRecorder(root_dir=tmp_path / "usage"),
        adapter_override=adapter,
    )
    request = LLMRequest(prompt="hello")
    first = asyncio.run(client.complete(request))
    second = asyncio.run(client.complete(request))
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert adapter.calls == 1


def test_client_surfaces_provider_error(tmp_path: Path) -> None:
    """Provider failures should surface as LLM provider errors."""

    settings = _IsolatedSettings(
        aeat_llm_provider=LLMProviderSetting.ANTHROPIC,
        aeat_llm_model="claude-sonnet-4-6",
        aeat_llm_cache_dir=tmp_path / "cache",
        aeat_llm_usage_dir=tmp_path / "usage",
    )
    client = LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=tmp_path / "cache"),
        usage_recorder=UsageRecorder(root_dir=tmp_path / "usage"),
        adapter_override=_DeterministicAdapter(error_mode="provider"),
    )
    with pytest.raises(LLMProviderError):
        asyncio.run(client.complete(LLMRequest(prompt="hello")))


def test_client_surfaces_rate_limit_error(tmp_path: Path) -> None:
    """Rate-limit failures should surface as the dedicated rate-limit error."""

    settings = _IsolatedSettings(
        aeat_llm_provider=LLMProviderSetting.ANTHROPIC,
        aeat_llm_model="claude-sonnet-4-6",
        aeat_llm_cache_dir=tmp_path / "cache",
        aeat_llm_usage_dir=tmp_path / "usage",
    )
    client = LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=tmp_path / "cache"),
        usage_recorder=UsageRecorder(root_dir=tmp_path / "usage"),
        adapter_override=_DeterministicAdapter(error_mode="rate-limit"),
    )
    with pytest.raises(LLMRateLimitError):
        asyncio.run(client.complete(LLMRequest(prompt="hello")))


def test_secretstr_masks_llm_keys_in_settings_repr() -> None:
    """LLM API keys should never appear in repr or serialized JSON."""

    settings = _IsolatedSettings(
        aeat_llm_provider=LLMProviderSetting.ANTHROPIC,
        aeat_llm_model="claude-sonnet-4-6",
        aeat_llm_anthropic_api_key=SecretStr("sk-test-secret"),
    )
    assert "sk-test-secret" not in repr(settings)
    assert "sk-test-secret" not in settings.model_dump_json()
