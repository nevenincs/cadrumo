"""Smoke tests for the :mod:`cadrumo.adapters.outbound.llm` subpackage."""

import pytest

from ..cache import LLMCache
from ..client import LLMClient
from ..errors import LLMError
from ..models import LLMRequest, LLMResponse, PromptRegistry
from ..run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder, LLMRunTelemetrySummary
from ..usage import UsageRecorder

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_smoke_llm_key_symbols_are_importable() -> None:
    """Key concrete symbols are importable and have the expected types."""
    import inspect

    assert inspect.isclass(LLMClient), "LLMClient must be a class"
    assert inspect.isclass(LLMCache), "LLMCache must be a class"
    assert inspect.isclass(LLMRequest), "LLMRequest must be a class"
    assert inspect.isclass(LLMResponse), "LLMResponse must be a class"
    assert inspect.isclass(PromptRegistry), "PromptRegistry must be a class"
    assert inspect.isclass(LLMError), "LLMError must be a class"
    assert inspect.isclass(LLMRunRecord), "LLMRunRecord must be a class"
    assert inspect.isclass(LLMRunTelemetryRecorder), "LLMRunTelemetryRecorder must be a class"
    assert inspect.isclass(LLMRunTelemetrySummary), "LLMRunTelemetrySummary must be a class"
    assert inspect.isclass(UsageRecorder), "UsageRecorder must be a class"
    assert issubclass(LLMError, Exception), "LLMError must inherit from Exception"
