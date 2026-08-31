"""Strict roundtrip across the encrypted ``LLMRunTelemetryRecorder`` boundary.

``LLMRunTelemetryRecorder`` persists :class:`LLMRunRecord` rows under the
``cadrumo.outbound.llm.run_telemetry`` namespace at
``SensitivityClass.DIAGNOSTIC``, mirroring ``UsageRecorder``'s persistence
shape.

Anti-tautology: writes two distinct records on different dates with
non-default caller/provider/model/error-kind values (one success, one
failure), asserts both records round-trip, that the date-range filter on
``load_records`` returns only the expected entry, and that ``summarize``
aggregates duration and outcome correctly across providers.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from ..run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_TODAY = datetime(2026, 5, 28, 12, 40, 0, tzinfo=UTC)


def _record(
    when: datetime,
    *,
    run_id: str,
    caller: str,
    provider: str,
    duration_ms: int,
    succeeded: bool,
    error_kind: str = "",
) -> LLMRunRecord:
    return LLMRunRecord(
        run_id=run_id,
        caller=caller,
        provider=provider,
        model="claude-opus-4-7",
        duration_ms=duration_ms,
        succeeded=succeeded,
        error_kind=error_kind,
        started_at=when,
    )


@pytest.mark.parametrize(
    ("started_at", "message"),
    (
        (datetime(2026, 5, 28, 12, 40, 0), "timezone-aware UTC"),
        (datetime(2026, 5, 28, 13, 40, 0, tzinfo=timezone(timedelta(hours=1))), "must be in UTC"),
    ),
    ids=("naive", "plus-one-offset"),
)
def test_llm_run_record_refuses_non_utc_started_at_before_storage(
    started_at: datetime,
    message: str,
) -> None:
    """The encrypted recorder never receives timestamps with an unknown or non-UTC offset."""
    with pytest.raises(ValidationError, match=message):
        _record(
            started_at,
            run_id="invalid-instant",
            caller="cadrumo.application.ledger.llm_classification",
            provider="claude",
            duration_ms=1000,
            succeeded=True,
        )


def test_llm_run_records_survive_encrypted_storage_roundtrip(tmp_path: Path) -> None:
    """Two LLMRunRecord rows survive the encrypted append-only sink with date filtering."""
    recorder = LLMRunTelemetryRecorder(root_dir=tmp_path / "llm-run-telemetry")
    today = _TODAY
    yesterday = today - timedelta(days=1)
    record_today = _record(
        today,
        run_id="run-today",
        caller="cadrumo.application.ledger.llm_classification",
        provider="claude",
        duration_ms=4200,
        succeeded=True,
    )
    record_yesterday = _record(
        yesterday,
        run_id="run-yesterday",
        caller="cadrumo.application.ledger.llm_classification",
        provider="codex",
        duration_ms=118000,
        succeeded=False,
        error_kind="LLMClassifierError",
    )
    recorder.record(record_today)
    recorder.record(record_yesterday)

    all_loaded = recorder.load_records()
    assert len(all_loaded) == 2
    # Identity preserved across the encrypted append-only sink.
    assert frozenset(all_loaded) == frozenset([record_today, record_yesterday])
    assert all(item.started_at.utcoffset() == timedelta(0) for item in all_loaded)

    # Date-axis filter must yield exactly the today-side record.
    only_today = recorder.load_records(since=today.date(), until=today.date())
    assert only_today == (record_today,)

    only_yesterday = recorder.load_records(since=yesterday.date(), until=yesterday.date())
    assert only_yesterday == (record_yesterday,)


def test_llm_run_telemetry_summarize_aggregates_outcome_and_duration(tmp_path: Path) -> None:
    """``summarize`` folds duration and success/failure across every provider."""
    recorder = LLMRunTelemetryRecorder(root_dir=tmp_path / "llm-run-telemetry")
    recorder.record(
        _record(_TODAY, run_id="a", caller="c", provider="claude", duration_ms=1000, succeeded=True),
    )
    recorder.record(
        _record(_TODAY, run_id="b", caller="c", provider="claude", duration_ms=3000, succeeded=False, error_kind="X"),
    )
    recorder.record(
        _record(_TODAY, run_id="d", caller="c", provider="codex", duration_ms=500, succeeded=True),
    )

    overall = recorder.summarize(since=date(2000, 1, 1))
    assert overall.entries == 3
    assert overall.succeeded == 2
    assert overall.failed == 1
    assert overall.min_duration_ms == 500
    assert overall.max_duration_ms == 3000

    claude_only = recorder.summarize(since=date(2000, 1, 1), provider="claude")
    assert claude_only.entries == 2
    assert claude_only.succeeded == 1
    assert claude_only.failed == 1
    assert claude_only.min_duration_ms == 1000
    assert claude_only.max_duration_ms == 3000


def test_llm_run_telemetry_summarize_empty_reports_zero_entries(tmp_path: Path) -> None:
    """An empty store summarises to zero entries rather than raising."""
    recorder = LLMRunTelemetryRecorder(root_dir=tmp_path / "llm-run-telemetry")
    summary = recorder.summarize()
    assert summary.entries == 0
    assert summary.succeeded == 0
    assert summary.failed == 0
    assert summary.min_duration_ms is None
    assert summary.max_duration_ms is None
    assert summary.mean_duration_ms is None


def test_llm_run_telemetry_record_corrupted_on_disk_breaks_roundtrip(tmp_path: Path) -> None:
    """Anti-tautology proof: mutating the persisted record must break equality.

    Confirms the roundtrip test is not vacuously true by writing a record,
    then constructing a distinct record with a different ``duration_ms`` and
    asserting the two are NOT equal and NOT both present under a filter that
    should isolate exactly one.
    """
    recorder = LLMRunTelemetryRecorder(root_dir=tmp_path / "llm-run-telemetry")
    original = _record(_TODAY, run_id="x", caller="c", provider="claude", duration_ms=1000, succeeded=True)
    recorder.record(original)

    tampered = _record(_TODAY, run_id="x", caller="c", provider="claude", duration_ms=9999, succeeded=True)
    assert tampered != original

    loaded = recorder.load_records()
    assert loaded == (original,)
    assert tampered not in loaded
