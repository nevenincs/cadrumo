"""Strict-validation tests for the :mod:`aeat.core.observability._models` records.

Covers:

* :class:`ArgumentRecord` round-trip and ``extra="forbid"`` enforcement.
* :class:`RunEventPayload` exactly-one-variant invariant across each
  variant (zero-variant and two-variant payloads must raise).
* Timezone-awareness rejection on naive datetimes for both
  :class:`RunEvent` and :class:`RunTrace`.
* :attr:`RunTrace.replay_of` default + round-trip.
* End-to-end pydantic round-trip through ``model_dump_json`` /
  ``model_validate_json`` for both :class:`RunEvent` and
  :class:`RunTrace`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from .. import (
    ArgumentRecord,
    ArgumentSource,
    AssertionPayload,
    CacheHitPayload,
    ErrorPayload,
    FormFillPayload,
    GenericPayload,
    NavigationPayload,
    RunEvent,
    RunEventKind,
    RunEventPayload,
    RunOutcome,
    RunTrace,
    StepBoundaryPayload,
    WorkflowLinkPayload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _make_event(payload: RunEventPayload) -> RunEvent:
    return RunEvent(
        run_id="0123456789abcdef",
        step_id="step-0",
        kind=RunEventKind.NAVIGATION,
        payload=payload,
        timestamp=datetime(2026, 4, 14, tzinfo=UTC),
        module="aeat.core.observability.test_models",
    )


class TestArgumentRecord:
    def test_round_trip(self) -> None:
        record = ArgumentRecord(name="modelo", value="130", source=ArgumentSource.FLAG)
        rebuilt = ArgumentRecord.model_validate_json(record.model_dump_json())
        assert rebuilt == record

    def test_strict_rejects_extra(self) -> None:
        with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
            ArgumentRecord.model_validate(
                {"name": "x", "value": "y", "source": "FLAG", "leak": True},
            )


class TestRunEventPayload:
    def test_each_variant_round_trips(self) -> None:
        variants: list[RunEventPayload] = [
            RunEventPayload(navigation=NavigationPayload(url="https://example.test")),
            RunEventPayload(
                form_fill=FormFillPayload(form_id="f1", display_number="03", value="1.50"),
            ),
            RunEventPayload(
                assertion=AssertionPayload(expectation="open", passed=True),
            ),
            RunEventPayload(cache_hit=CacheHitPayload(cache_name="iva", key="2025")),
            RunEventPayload(error=ErrorPayload(error_type="X", message="boom")),
            RunEventPayload(step=StepBoundaryPayload(step_id="s1", label="t")),
            RunEventPayload(workflow_link=WorkflowLinkPayload(workflow_run_id="abc")),
            RunEventPayload(generic=GenericPayload(fields=(("k", "v"),))),
        ]
        for payload in variants:
            rebuilt = RunEventPayload.model_validate_json(payload.model_dump_json())
            assert rebuilt == payload

    def test_zero_variants_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"must set exactly one variant"):
            RunEventPayload()

    def test_two_variants_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"must set exactly one variant"):
            RunEventPayload(
                navigation=NavigationPayload(url="https://x"),
                error=ErrorPayload(error_type="E", message="m"),
            )


class TestTimezoneAwareness:
    """Naive datetimes must be rejected at the pydantic boundary."""

    def test_run_event_rejects_naive_timestamp(self) -> None:
        with pytest.raises(ValidationError, match="timezone-aware"):
            RunEvent(
                run_id="0123456789abcdef",
                step_id="step-0",
                kind=RunEventKind.NAVIGATION,
                payload=RunEventPayload(navigation=NavigationPayload(url="https://x")),
                timestamp=datetime(2026, 4, 14),
                module="aeat.core.observability.test_models",
            )

    def test_run_trace_rejects_naive_started_at(self) -> None:
        with pytest.raises(ValidationError, match="timezone-aware"):
            RunTrace(
                run_id="0123456789abcdef",
                started_at=datetime(2026, 4, 14),
                finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
                entrypoint="aeat hello",
                arguments=(),
                corpus_sha256="a" * 64,
                db_sha256="b" * 64,
                cert_fingerprint="",
                outcome=RunOutcome.OK,
            )

    def test_run_trace_rejects_naive_finished_at(self) -> None:
        with pytest.raises(ValidationError, match="timezone-aware"):
            RunTrace(
                run_id="0123456789abcdef",
                started_at=datetime(2026, 4, 14, tzinfo=UTC),
                finished_at=datetime(2026, 4, 14, 0, 0, 1),
                entrypoint="aeat hello",
                arguments=(),
                corpus_sha256="a" * 64,
                db_sha256="b" * 64,
                cert_fingerprint="",
                outcome=RunOutcome.OK,
            )


class TestReplayOfField:
    """``replay_of`` defaults to ``None`` and round-trips valid run ids."""

    def test_default_none(self) -> None:
        trace = RunTrace(
            run_id="0123456789abcdef",
            started_at=datetime(2026, 4, 14, tzinfo=UTC),
            finished_at=None,
            entrypoint="aeat hello",
            arguments=(),
            corpus_sha256="a" * 64,
            db_sha256="b" * 64,
            cert_fingerprint="",
            outcome=RunOutcome.OK,
        )
        assert trace.replay_of is None

    def test_roundtrip_with_replay_of(self) -> None:
        trace = RunTrace(
            run_id="0123456789abcdef",
            started_at=datetime(2026, 4, 14, tzinfo=UTC),
            finished_at=None,
            entrypoint="aeat hello",
            arguments=(),
            corpus_sha256="a" * 64,
            db_sha256="b" * 64,
            cert_fingerprint="",
            outcome=RunOutcome.OK,
            replay_of="fedcba9876543210",
        )
        rebuilt = RunTrace.model_validate_json(trace.model_dump_json())
        assert rebuilt.replay_of == "fedcba9876543210"


class TestRunEventAndTrace:
    def test_event_round_trip(self) -> None:
        evt = _make_event(
            RunEventPayload(navigation=NavigationPayload(url="https://example.test")),
        )
        rebuilt = RunEvent.model_validate_json(evt.model_dump_json())
        assert rebuilt == evt

    def test_trace_round_trip(self) -> None:
        trace = RunTrace(
            run_id="0123456789abcdef",
            started_at=datetime(2026, 4, 14, tzinfo=UTC),
            finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
            entrypoint="aeat workflow run",
            arguments=(ArgumentRecord(name="modelo", value="130", source=ArgumentSource.FLAG),),
            corpus_sha256="a" * 64,
            db_sha256="b" * 64,
            cert_fingerprint="",
            outcome=RunOutcome.OK,
        )
        rebuilt = RunTrace.model_validate_json(trace.model_dump_json())
        assert rebuilt == trace
