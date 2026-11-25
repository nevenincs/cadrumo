"""Behaviour tests for the public LLM client: cache, usage and run records.

The completion cases cross the production :class:`LLMClient` and the real
agent adapter. The agent service behind the model-run port is a recording
stand-in, so what reached the service is observed rather than assumed; the
service side has its own tests.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from cadrumo_client.contracts.model_runs import ModelRunRefusalCode

from .....core.config_support import LLMProvider
from .....core.model_roles import ModelRole
from .....tests.fixtures.settings import EnvFileFreeSettings
from ....persistence.llm.run_records import LLMRunRecorder
from ..client import LLMClient
from ..errors import LLMProviderError
from ..models import LLMRequest
from .model_run_support import ON_HOST_LANE, serving_agent

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_LANE_MODEL = f"{ON_HOST_LANE.provider_id}/{ON_HOST_LANE.transport}/{ON_HOST_LANE.model}"


def _settings(tmp_path: Path) -> EnvFileFreeSettings:
    return EnvFileFreeSettings(cadrumo_storage_root=tmp_path)


def _client(tmp_path: Path, *, run_recorder: LLMRunRecorder | None = None) -> LLMClient:
    return LLMClient(settings=_settings(tmp_path), run_record_recorder=run_recorder)


def _request() -> LLMRequest:
    return LLMRequest(prompt="hello", model_role=ModelRole.TEXT_EXTRACTION)


def test_client_uses_cache_before_calling_provider(tmp_path: Path) -> None:
    """A repeated request should hit the cache instead of running the model again."""
    with serving_agent(lane=ON_HOST_LANE, replies=("agent completion",)) as service:
        client = _client(tmp_path)
        first = asyncio.run(client.complete(_request()))
        second = asyncio.run(client.complete(_request()))

    assert first.text == "agent completion"
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert len(service.runs) == 1


def test_client_surfaces_provider_error(tmp_path: Path) -> None:
    """A failed run surfaces as an LLM provider error naming the agent route."""
    with (
        serving_agent(lane=ON_HOST_LANE, run_refusal=ModelRunRefusalCode.RUN_FAILED),
        pytest.raises(LLMProviderError) as raised,
    ):
        asyncio.run(_client(tmp_path).complete(_request()))

    assert raised.value.context is not None
    assert raised.value.context["provider"] == LLMProvider.AGENT.value
    assert raised.value.context["model_run_refusal"] == ModelRunRefusalCode.RUN_FAILED.value


def test_client_records_run_record_on_success(tmp_path: Path) -> None:
    """A successful run records one succeeded run-timing record."""
    run_recorder = LLMRunRecorder(root_dir=tmp_path / "run-record")
    with serving_agent(lane=ON_HOST_LANE, replies=("agent completion",)):
        asyncio.run(_client(tmp_path, run_recorder=run_recorder).complete(_request()))

    records = run_recorder.load_records()
    assert len(records) == 1
    record = records[0]
    assert record.succeeded is True
    assert record.error_kind == ""
    assert record.provider == LLMProvider.AGENT.value
    assert record.model == _LANE_MODEL
    assert record.duration_ms >= 0


def test_client_cache_hit_does_not_record_a_second_run(tmp_path: Path) -> None:
    """A cache hit must not append a second run-timing record."""
    run_recorder = LLMRunRecorder(root_dir=tmp_path / "run-record")
    with serving_agent(lane=ON_HOST_LANE, replies=("agent completion",)):
        client = _client(tmp_path, run_recorder=run_recorder)
        asyncio.run(client.complete(_request()))
        asyncio.run(client.complete(_request()))

    assert len(run_recorder.load_records()) == 1


def test_client_records_run_record_on_provider_failure(tmp_path: Path) -> None:
    """A failed run records one failed run naming the error kind."""
    run_recorder = LLMRunRecorder(root_dir=tmp_path / "run-record")
    with (
        serving_agent(lane=ON_HOST_LANE, run_refusal=ModelRunRefusalCode.RUN_FAILED),
        pytest.raises(LLMProviderError),
    ):
        asyncio.run(_client(tmp_path, run_recorder=run_recorder).complete(_request()))

    records = run_recorder.load_records()
    assert len(records) == 1
    assert records[0].succeeded is False
    assert records[0].error_kind == "LLMProviderError"
