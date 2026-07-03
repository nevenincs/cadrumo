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

from .....core.config import LLMProviderSetting
from .....tests.fixtures.settings import EnvFileFreeSettings
from .. import (
    LLMCache,
    LLMClient,
    LLMProviderError,
    LLMRateLimitError,
    LLMRequest,
    LLMRunTelemetryRecorder,
    UsageRecorder,
)
from .._providers import ProviderRequest
from .._providers.deterministic import _DeterministicAdapter

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_provider_package_facade_does_not_reexport_private_adapters() -> None:
    """Private adapter types must stay on their owning modules."""

    from .. import _providers

    assert "_ProviderAdapter" not in _providers.__dict__
    assert "_DeterministicAdapter" not in _providers.__dict__
    assert all(not name.startswith("_") for name in _providers.__all__)
    assert not hasattr(_providers, "_ProviderAdapter")
    assert not hasattr(_providers, "_DeterministicAdapter")


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

    settings = EnvFileFreeSettings(
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

    settings = EnvFileFreeSettings(
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

    settings = EnvFileFreeSettings(
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


def test_client_records_run_telemetry_on_success(tmp_path: Path) -> None:
    """A successful completion records one succeeded run-timing record."""

    settings = EnvFileFreeSettings(
        aeat_llm_provider=LLMProviderSetting.ANTHROPIC,
        aeat_llm_model="claude-sonnet-4-6",
        aeat_llm_cache_dir=tmp_path / "cache",
        aeat_llm_usage_dir=tmp_path / "usage",
        aeat_llm_run_telemetry_dir=tmp_path / "run-telemetry",
    )
    run_recorder = LLMRunTelemetryRecorder(root_dir=tmp_path / "run-telemetry")
    client = LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=tmp_path / "cache"),
        usage_recorder=UsageRecorder(root_dir=tmp_path / "usage"),
        run_telemetry_recorder=run_recorder,
        adapter_override=_DeterministicAdapter(response_text="run-telemetry-check"),
    )
    asyncio.run(client.complete(LLMRequest(prompt="hello")))

    records = run_recorder.load_records()
    assert len(records) == 1
    record = records[0]
    assert record.succeeded is True
    assert record.error_kind == ""
    assert record.provider == "ANTHROPIC"
    assert record.model == "claude-sonnet-4-6"
    assert record.duration_ms >= 0


def test_client_cache_hit_does_not_record_a_second_run(tmp_path: Path) -> None:
    """A cache-hit completion must not append a second run-timing record.

    Only the real provider call is diagnostically interesting for "how long
    did the LLM take"; a cache hit is near-instant and would only dilute the
    duration distribution.
    """

    settings = EnvFileFreeSettings(
        aeat_llm_provider=LLMProviderSetting.ANTHROPIC,
        aeat_llm_model="claude-sonnet-4-6",
        aeat_llm_cache_dir=tmp_path / "cache",
        aeat_llm_usage_dir=tmp_path / "usage",
        aeat_llm_run_telemetry_dir=tmp_path / "run-telemetry",
    )
    run_recorder = LLMRunTelemetryRecorder(root_dir=tmp_path / "run-telemetry")
    client = LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=tmp_path / "cache"),
        usage_recorder=UsageRecorder(root_dir=tmp_path / "usage"),
        run_telemetry_recorder=run_recorder,
        adapter_override=_DeterministicAdapter(response_text="cached-run"),
    )
    request = LLMRequest(prompt="hello")
    asyncio.run(client.complete(request))
    asyncio.run(client.complete(request))

    assert len(run_recorder.load_records()) == 1


def test_client_records_run_telemetry_on_provider_failure(tmp_path: Path) -> None:
    """A provider failure records one failed run-timing record naming the error kind."""

    settings = EnvFileFreeSettings(
        aeat_llm_provider=LLMProviderSetting.ANTHROPIC,
        aeat_llm_model="claude-sonnet-4-6",
        aeat_llm_cache_dir=tmp_path / "cache",
        aeat_llm_usage_dir=tmp_path / "usage",
        aeat_llm_run_telemetry_dir=tmp_path / "run-telemetry",
    )
    run_recorder = LLMRunTelemetryRecorder(root_dir=tmp_path / "run-telemetry")
    client = LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=tmp_path / "cache"),
        usage_recorder=UsageRecorder(root_dir=tmp_path / "usage"),
        run_telemetry_recorder=run_recorder,
        adapter_override=_DeterministicAdapter(error_mode="provider"),
    )
    with pytest.raises(LLMProviderError):
        asyncio.run(client.complete(LLMRequest(prompt="hello")))

    records = run_recorder.load_records()
    assert len(records) == 1
    assert records[0].succeeded is False
    assert records[0].error_kind == "LLMProviderError"


def test_secretstr_masks_llm_keys_in_settings_repr() -> None:
    """LLM API keys should never appear in repr or serialized JSON."""

    settings = EnvFileFreeSettings(
        aeat_llm_provider=LLMProviderSetting.ANTHROPIC,
        aeat_llm_model="claude-sonnet-4-6",
        aeat_llm_anthropic_api_key=SecretStr("sk-test-secret"),
    )
    assert "sk-test-secret" not in repr(settings)
    assert "sk-test-secret" not in settings.model_dump_json()
