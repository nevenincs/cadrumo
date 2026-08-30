"""Behaviour tests for the public LLM client through the local provider.

The completion cases cross the production :class:`LLMClient`,
:class:`LocalAdapter`, and HTTP transport against an Ollama-shaped loopback
service. This keeps the provider boundary real while remaining fully on-host.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from queue import Queue
from typing import override

import pytest
from pydantic import SecretStr

from ...adapters.outbound.llm import LLMCache, LLMRunTelemetryRecorder, UsageRecorder
from ...core.config import LLMProvider, override_settings
from ...tests.fixtures.settings import EnvFileFreeSettings
from ...tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from ..client import LLMClient
from ..errors import LLMProviderError, LLMRateLimitError
from ..models import LLMRequest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _settings(tmp_path: Path) -> EnvFileFreeSettings:
    return EnvFileFreeSettings(
        cadrumo_llm_provider=LLMProvider.LOCAL,
        cadrumo_llm_model="gpt-oss",
        cadrumo_llm_cache_dir=tmp_path / "probe-cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_telemetry_dir=tmp_path / "run-telemetry",
    )


def _client(tmp_path: Path, *, run_recorder: LLMRunTelemetryRecorder | None = None) -> LLMClient:
    settings = _settings(tmp_path)
    return LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
        usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
        run_telemetry_recorder=run_recorder,
    )


@contextmanager
def _serve_ollama(status: HTTPStatus = HTTPStatus.OK) -> Iterator[tuple[str, Queue[dict[str, object]]]]:
    events: Queue[dict[str, object]] = Queue()

    class _OllamaEndpoint(SilentLoopbackHandler):
        @override
        def do_POST(self) -> None:
            events.put({"path": self.path, "body": read_json_body(self)})
            payload = ollama_chat_reply(" local completion ") if status is HTTPStatus.OK else {"error": status.phrase}
            write_json_response(
                self,
                payload,
                status=status,
                extra_headers={"retry-after": "0.01"} if status is HTTPStatus.TOO_MANY_REQUESTS else None,
            )

    with serving_loopback(_OllamaEndpoint, path="/api/chat") as endpoint:
        yield endpoint, events


def test_provider_package_facade_does_not_reexport_private_adapters() -> None:
    """Private adapter types must stay on their owning modules."""
    from .. import providers as _providers

    assert "_ProviderAdapter" not in _providers.__dict__
    assert all(not name.startswith("_") for name in _providers.__all__)
    assert not hasattr(_providers, "_ProviderAdapter")


def test_client_uses_cache_before_calling_provider(tmp_path: Path) -> None:
    """A repeated request should hit the cache instead of re-calling Ollama."""
    with _serve_ollama() as (endpoint, events), override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        client = _client(tmp_path)
        request = LLMRequest(prompt="hello")
        first = asyncio.run(client.complete(request))
        second = asyncio.run(client.complete(request))

    assert first.text == "local completion"
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert events.qsize() == 1


def test_client_surfaces_provider_error(tmp_path: Path) -> None:
    """Provider failures should surface as LLM provider errors."""
    with (
        _serve_ollama(HTTPStatus.SERVICE_UNAVAILABLE) as (endpoint, _events),
        override_settings(cadrumo_llm_ollama_chat_url=endpoint),
        pytest.raises(LLMProviderError) as raised,
    ):
        asyncio.run(_client(tmp_path).complete(LLMRequest(prompt="hello")))
    assert raised.value.context == {
        "http_status": HTTPStatus.SERVICE_UNAVAILABLE,
        "model": "gpt-oss",
        "provider_name": LLMProvider.LOCAL.value,
    }


def test_client_surfaces_rate_limit_error(tmp_path: Path) -> None:
    """Rate-limit failures should surface as the dedicated rate-limit error."""
    with (
        _serve_ollama(HTTPStatus.TOO_MANY_REQUESTS) as (endpoint, _events),
        override_settings(cadrumo_llm_ollama_chat_url=endpoint),
        pytest.raises(LLMRateLimitError) as exc_info,
    ):
        asyncio.run(_client(tmp_path).complete(LLMRequest(prompt="hello")))

    assert exc_info.value.retry_after_seconds == pytest.approx(0.01)


def test_client_records_run_telemetry_on_success(tmp_path: Path) -> None:
    """A successful provider call records one succeeded run-timing record."""
    run_recorder = LLMRunTelemetryRecorder(root_dir=tmp_path / "run-telemetry")
    with _serve_ollama() as (endpoint, _events), override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        asyncio.run(_client(tmp_path, run_recorder=run_recorder).complete(LLMRequest(prompt="hello")))

    records = run_recorder.load_records()
    assert len(records) == 1
    record = records[0]
    assert record.succeeded is True
    assert record.error_kind == ""
    assert record.provider == "LOCAL"
    assert record.model == "gpt-oss"
    assert record.duration_ms >= 0


def test_client_cache_hit_does_not_record_a_second_run(tmp_path: Path) -> None:
    """A cache hit must not append a second provider run-timing record."""
    run_recorder = LLMRunTelemetryRecorder(root_dir=tmp_path / "run-telemetry")
    with _serve_ollama() as (endpoint, _events), override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        client = _client(tmp_path, run_recorder=run_recorder)
        request = LLMRequest(prompt="hello")
        asyncio.run(client.complete(request))
        asyncio.run(client.complete(request))

    assert len(run_recorder.load_records()) == 1


def test_client_records_run_telemetry_on_provider_failure(tmp_path: Path) -> None:
    """A provider failure records one failed run naming the error kind."""
    run_recorder = LLMRunTelemetryRecorder(root_dir=tmp_path / "run-telemetry")
    with (
        _serve_ollama(HTTPStatus.SERVICE_UNAVAILABLE) as (endpoint, _events),
        override_settings(cadrumo_llm_ollama_chat_url=endpoint),
        pytest.raises(LLMProviderError),
    ):
        asyncio.run(_client(tmp_path, run_recorder=run_recorder).complete(LLMRequest(prompt="hello")))

    records = run_recorder.load_records()
    assert len(records) == 1
    assert records[0].succeeded is False
    # A 5xx is the transient half of the provider boundary, so the recorded kind
    # names the class the retry policy actually classified on.
    assert records[0].error_kind == "LLMTransientTransportError"


def test_secretstr_masks_llm_keys_in_settings_repr() -> None:
    """LLM API keys should never appear in repr or serialized JSON."""
    settings = EnvFileFreeSettings(
        cadrumo_llm_provider=LLMProvider.ANTHROPIC,
        cadrumo_llm_model="claude-sonnet-4-6",
        cadrumo_llm_anthropic_api_key=SecretStr("sk-test-secret"),
    )
    assert "sk-test-secret" not in repr(settings)
    assert "sk-test-secret" not in settings.model_dump_json()
