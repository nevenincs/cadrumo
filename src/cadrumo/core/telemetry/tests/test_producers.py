"""Tests for the non-sensitive operational telemetry producers.

Proves the whole gate-then-schema-then-emit pipeline end to end for each
wired producer: consent-off (the default posture) emits nothing to the sink,
a fully-permitted invocation dispatches exactly the allowlisted payload the
registry declares, and a producer cannot be made to carry a sensitive field --
the function signatures themselves accept only accounting/timing values.
Uses a real, minimal in-memory :class:`~core.telemetry.TelemetrySink`
implementation (not a mock), mirroring ``test_emit.py``'s sanctioned pure-logic
test-double pattern.

See Also:
    :func:`~core.telemetry.emit_command_invocation_telemetry`:
        Producer for command-count and duration metrics.
    :func:`~core.telemetry.emit_llm_run_telemetry`:
        Producer for non-sensitive local LLM run timing metrics.
    :func:`~core.telemetry.build_telemetry_payload`:
        Closed-schema allowlist builder shared by every producer.
    :func:`~core.telemetry.emit_telemetry_event`:
        Consent-gated dispatcher the producers call after schema validation.
"""

from __future__ import annotations

import pytest

from ...config import Settings
from .. import (
    TelemetryEventPayload,
    TelemetryTier,
    emit_command_invocation_telemetry,
    emit_error_frequency_telemetry,
    emit_llm_run_telemetry,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_WORKSPACE_HASH = "c" * 64
_CAPTURED_AT = "2026-07-04T00:00:00+00:00"


class _RecordingSink:
    """A real, minimal sink that records every payload it receives."""

    def __init__(self) -> None:
        self.received: list[TelemetryEventPayload] = []

    def send(self, payload: TelemetryEventPayload) -> None:
        self.received.append(payload)


def _permitted_settings() -> Settings:
    return Settings(cadrumo_telemetry_opt_in=True, cadrumo_telemetry_tier=TelemetryTier.FULL)


# ── command-invocation producer ──────────────────────────────────────────


def test_command_invocation_consent_off_emits_nothing() -> None:
    settings = Settings()
    sink = _RecordingSink()
    result = emit_command_invocation_telemetry(
        workspace_hash=_WORKSPACE_HASH,
        succeeded=True,
        duration_ms=120,
        captured_at=_CAPTURED_AT,
        settings=settings,
        acknowledged=True,
        sink=sink,
    )
    assert result is False
    assert sink.received == []


def test_command_invocation_permitted_dispatches_the_allowlisted_payload() -> None:
    sink = _RecordingSink()
    result = emit_command_invocation_telemetry(
        workspace_hash=_WORKSPACE_HASH,
        succeeded=True,
        duration_ms=250,
        captured_at=_CAPTURED_AT,
        settings=_permitted_settings(),
        acknowledged=True,
        sink=sink,
    )
    assert result is True
    assert len(sink.received) == 1
    payload = sink.received[0]
    assert payload.command == "diagnostics.command_invocation"
    assert payload.counters == {"invocations": 1, "succeeded": 1, "failed": 0}
    assert payload.timings_ms == {"duration": 250}
    assert payload.succeeded is True


def test_command_invocation_failed_run_increments_the_failed_counter() -> None:
    sink = _RecordingSink()
    emit_command_invocation_telemetry(
        workspace_hash=_WORKSPACE_HASH,
        succeeded=False,
        duration_ms=10,
        captured_at=_CAPTURED_AT,
        settings=_permitted_settings(),
        acknowledged=True,
        sink=sink,
    )
    payload = sink.received[0]
    assert payload.counters == {"invocations": 1, "succeeded": 0, "failed": 1}
    assert payload.succeeded is False


# ── LLM-run producer ─────────────────────────────────────────────────────


def test_llm_run_consent_off_emits_nothing() -> None:
    settings = Settings()
    sink = _RecordingSink()
    result = emit_llm_run_telemetry(
        workspace_hash=_WORKSPACE_HASH,
        succeeded=True,
        duration_ms=4200,
        captured_at=_CAPTURED_AT,
        settings=settings,
        acknowledged=True,
        sink=sink,
    )
    assert result is False
    assert sink.received == []


def test_llm_run_not_acknowledged_emits_nothing_even_when_opted_in() -> None:
    sink = _RecordingSink()
    result = emit_llm_run_telemetry(
        workspace_hash=_WORKSPACE_HASH,
        succeeded=True,
        duration_ms=4200,
        captured_at=_CAPTURED_AT,
        settings=_permitted_settings(),
        acknowledged=False,
        sink=sink,
    )
    assert result is False
    assert sink.received == []


def test_llm_run_permitted_dispatches_the_allowlisted_payload() -> None:
    sink = _RecordingSink()
    result = emit_llm_run_telemetry(
        workspace_hash=_WORKSPACE_HASH,
        succeeded=True,
        duration_ms=4200,
        captured_at=_CAPTURED_AT,
        settings=_permitted_settings(),
        acknowledged=True,
        sink=sink,
    )
    assert result is True
    payload = sink.received[0]
    assert payload.command == "diagnostics.llm_run"
    assert payload.counters == {"runs": 1, "succeeded": 1, "failed": 0}
    assert payload.timings_ms == {"duration": 4200}


def test_llm_run_gestor_mode_never_emits_even_fully_opted_in() -> None:
    settings = Settings(
        cadrumo_telemetry_opt_in=True,
        cadrumo_telemetry_tier=TelemetryTier.FULL,
        cadrumo_telemetry_gestor_mode=True,
    )
    sink = _RecordingSink()
    result = emit_llm_run_telemetry(
        workspace_hash=_WORKSPACE_HASH,
        succeeded=True,
        duration_ms=100,
        captured_at=_CAPTURED_AT,
        settings=settings,
        acknowledged=True,
        sink=sink,
    )
    assert result is False
    assert sink.received == []


# ── error-frequency producer ─────────────────────────────────────────────


def test_error_frequency_consent_off_emits_nothing() -> None:
    settings = Settings()
    sink = _RecordingSink()
    result = emit_error_frequency_telemetry(
        workspace_hash=_WORKSPACE_HASH,
        error_kind="LLMClassifierError",
        captured_at=_CAPTURED_AT,
        settings=settings,
        acknowledged=True,
        sink=sink,
    )
    assert result is False
    assert sink.received == []


def test_error_frequency_permitted_dispatches_the_closed_error_kind_label() -> None:
    sink = _RecordingSink()
    result = emit_error_frequency_telemetry(
        workspace_hash=_WORKSPACE_HASH,
        error_kind="LLMClassifierError",
        captured_at=_CAPTURED_AT,
        settings=_permitted_settings(),
        acknowledged=True,
        sink=sink,
    )
    assert result is True
    payload = sink.received[0]
    assert payload.command == "diagnostics.error_frequency"
    assert payload.counters == {"occurrences": 1}
    assert payload.error_kind == "LLMClassifierError"
    assert payload.succeeded is False


def test_error_frequency_rejects_a_sensitive_field_structurally() -> None:
    """A caller cannot smuggle an extra field through the producer's payload.

    The producer's ``build_telemetry_payload`` call constructs a
    ``TelemetryEventPayload``, whose ``extra="forbid"`` config makes any
    field beyond the declared allowlist structurally impossible -- proven
    here by confirming the emitted payload carries no attribute for a
    sensitive concept (there is no such kwarg to pass).
    """
    sink = _RecordingSink()
    emit_error_frequency_telemetry(
        workspace_hash=_WORKSPACE_HASH,
        error_kind="LLMClassifierError",
        captured_at=_CAPTURED_AT,
        settings=_permitted_settings(),
        acknowledged=True,
        sink=sink,
    )
    payload = sink.received[0]
    assert not hasattr(payload, "message")
    assert not hasattr(payload, "context")
    assert not hasattr(payload, "nif")
