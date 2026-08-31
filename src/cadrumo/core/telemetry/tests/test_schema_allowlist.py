"""Tests proving the telemetry payload allowlist is structural, not a denylist.

Every assertion here constructs a real ``pydantic`` model and observes a real
validation failure (unknown field rejected) or a real schema-registry refusal
(unregistered metric key rejected) -- never a mocked scrub function. This is
the anti-tautology proof for the allowlist: a sensitive field must be
impossible to attach to the payload, not merely absent from today's producer
code.

See Also:
    :class:`~core.telemetry.TelemetryEventPayload`:
        Closed payload model whose fields are the transmission allowlist.
    :data:`~core.telemetry.TELEMETRY_METRIC_REGISTRY`:
        Registry that declares which counter and timing keys may be remote.
    :func:`~core.telemetry.build_telemetry_payload`:
        Builder that rejects unregistered metric keys before emission.
    :class:`~core.telemetry.TelemetrySchemaError`:
        Authoring-time refusal for producers that skip registry enrollment.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._schema import (
    TELEMETRY_METRIC_REGISTRY,
    CounterSpec,
    MetricSchema,
    TelemetryEventPayload,
    TimingSpec,
    build_telemetry_payload,
)
from ..errors import TelemetrySchemaError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_WORKSPACE_HASH = "a" * 64
_CAPTURED_AT = "2026-07-04T00:00:00+00:00"
_FORBIDDEN_METRIC_KEY_SUBSTRINGS = ("nif", "amount", "iban", "name", "description", "message", "path", "profile_id")
_FORBIDDEN_PAYLOAD_FIELDS = (
    "message",
    "context",
    "description",
    "path",
    "transaction_description",
    "profile_id",
    "amount",
    "raw_payload",
)


def test_registry_declares_only_the_wired_non_sensitive_operational_commands() -> None:
    """The metric registry is closed to exactly the commands with a real producer.

    This slice wires three non-sensitive operational producers (CLI
    command-invocation counting, local-LLM-run counting/timing, error-kind
    frequency counting). No other command is registered.
    """
    assert set(TELEMETRY_METRIC_REGISTRY) == {
        "diagnostics.command_invocation",
        "diagnostics.llm_run",
        "diagnostics.error_frequency",
    }


def test_every_registered_metric_key_is_remote_allowed_and_non_sensitive() -> None:
    """Every declared counter/timing on every registered command is a plain
    operational count or duration -- never a field shaped like financial or
    identity content.
    """
    for command, schema in TELEMETRY_METRIC_REGISTRY.items():
        for key, spec in {**schema.counters, **schema.timings_ms}.items():
            assert spec.remote_allowed is True, f"{command}:{key}"
            lowered = key.lower()
            assert not any(bad in lowered for bad in _FORBIDDEN_METRIC_KEY_SUBSTRINGS), f"{command}:{key}"


def test_payload_rejects_an_unknown_field_structurally() -> None:
    """A field not on the allowlist cannot be constructed onto the payload at all.

    This is the structural proof: ``extra="forbid"`` on the strict frozen
    config means pydantic raises before any scrub function would even run.
    """
    with pytest.raises(ValidationError):
        TelemetryEventPayload(
            workspace_hash=_WORKSPACE_HASH,
            command="diagnostics.run_health",
            succeeded=True,
            captured_at=_CAPTURED_AT,
            nif="12345678Z",
        )


def test_payload_has_no_free_text_or_identity_field() -> None:
    """None of the classic sensitive-content field names exist on the model.

    Enumerates the exact field names a naive telemetry payload would carry
    (free text, an amount, a profile identifier) and proves each one is
    rejected by the strict, ``extra=\"forbid\"`` schema.
    """
    for forbidden_field in _FORBIDDEN_PAYLOAD_FIELDS:
        with pytest.raises(ValidationError):
            TelemetryEventPayload(
                workspace_hash=_WORKSPACE_HASH,
                command="diagnostics.run_health",
                succeeded=True,
                captured_at=_CAPTURED_AT,
                **{forbidden_field: "sensitive-value"},  # type: ignore
            )


def test_payload_carries_only_the_declared_allowlisted_fields() -> None:
    payload = TelemetryEventPayload(
        workspace_hash=_WORKSPACE_HASH,
        command="diagnostics.run_health",
        counters={},
        timings_ms={},
        succeeded=True,
        error_kind=None,
        captured_at=_CAPTURED_AT,
    )
    assert set(type(payload).model_fields) == {
        "schema_version",
        "workspace_hash",
        "command",
        "counters",
        "timings_ms",
        "succeeded",
        "error_kind",
        "captured_at",
    }


def test_build_telemetry_payload_refuses_an_unregistered_command_with_counters() -> None:
    with pytest.raises(TelemetrySchemaError):
        build_telemetry_payload(
            workspace_hash=_WORKSPACE_HASH,
            command="diagnostics.not_a_registered_command",
            counters={"invocations": 1},
            succeeded=True,
            captured_at=_CAPTURED_AT,
        )


def test_build_telemetry_payload_with_no_counters_and_unregistered_command_is_fine() -> None:
    """A bare success/failure signal with no counters/timings needs no schema entry."""
    payload = build_telemetry_payload(
        workspace_hash=_WORKSPACE_HASH,
        command="diagnostics.not_a_registered_command",
        succeeded=True,
        captured_at=_CAPTURED_AT,
    )
    assert payload.counters == {}
    assert payload.timings_ms == {}


def test_build_telemetry_payload_refuses_an_unregistered_key_on_a_registered_command() -> None:
    schema = MetricSchema(
        command="diagnostics.probe",
        counters={"runs": CounterSpec(description="probe run count", remote_allowed=True)},
    )
    registry = {"diagnostics.probe": schema}
    with pytest.raises(TelemetrySchemaError):
        build_telemetry_payload(
            workspace_hash=_WORKSPACE_HASH,
            command="diagnostics.probe",
            counters={"unregistered_key": 1},
            succeeded=True,
            captured_at=_CAPTURED_AT,
            registry=registry,
        )


def test_build_telemetry_payload_drops_a_registered_but_not_remote_allowed_key() -> None:
    schema = MetricSchema(
        command="diagnostics.probe",
        counters={
            "runs": CounterSpec(description="probe run count", remote_allowed=True),
            "local_only_detail": CounterSpec(description="local-only detail", remote_allowed=False),
        },
        timings_ms={"duration": TimingSpec(description="duration", remote_allowed=False)},
    )
    registry = {"diagnostics.probe": schema}
    payload = build_telemetry_payload(
        workspace_hash=_WORKSPACE_HASH,
        command="diagnostics.probe",
        counters={"runs": 3, "local_only_detail": 99},
        timings_ms={"duration": 42},
        succeeded=True,
        captured_at=_CAPTURED_AT,
        registry=registry,
    )
    assert payload.counters == {"runs": 3}
    assert payload.timings_ms == {}


def test_build_telemetry_payload_keeps_a_registered_remote_allowed_key() -> None:
    schema = MetricSchema(
        command="diagnostics.probe",
        counters={"runs": CounterSpec(description="probe run count", remote_allowed=True)},
        timings_ms={"duration": TimingSpec(description="duration", remote_allowed=True)},
    )
    registry = {"diagnostics.probe": schema}
    payload = build_telemetry_payload(
        workspace_hash=_WORKSPACE_HASH,
        command="diagnostics.probe",
        counters={"runs": 3},
        timings_ms={"duration": 42},
        succeeded=True,
        captured_at=_CAPTURED_AT,
        registry=registry,
    )
    assert payload.counters == {"runs": 3}
    assert payload.timings_ms == {"duration": 42}
