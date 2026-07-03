"""Real-behavior tests for :func:`aeat.application.diagnostics_run_health.build_run_health_report`.

Exercises the aggregator against a real
:class:`~aeat.adapters.outbound.llm.LLMRunTelemetryRecorder` (real encrypted
secure-object persistence, no mocks). The auth-session half is verified with
an injected :class:`~aeat.application.auth.AuthTestResult` -- ``auth_probe``
is a first-class dependency-injection seam the function accepts precisely so
callers can supply a real, previously-constructed probe result without
re-invoking the live probe on every call; this keeps the test independent of
the auth package's own (separately-tested) probe machinery.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ...adapters.outbound.llm import LLMRunRecord, LLMRunTelemetryRecorder
from ...application.auth import AuthTestResult
from ...tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ..diagnostics_run_health import build_run_health_report, list_recent_runs

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "55555555-5555-4555-8555-555555555555"


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as p:
        yield p


def _seed(recorder: LLMRunTelemetryRecorder) -> None:
    recorder.record(
        LLMRunRecord(
            run_id="a",
            caller="test",
            provider="llm:claude:test-model",
            duration_ms=1000,
            succeeded=True,
            started_at=datetime(2026, 4, 1, tzinfo=UTC),
        ),
    )
    recorder.record(
        LLMRunRecord(
            run_id="b",
            caller="test",
            provider="llm:claude:test-model",
            duration_ms=9000,
            succeeded=False,
            error_kind="LLMClassifierError",
            started_at=datetime(2026, 4, 2, tzinfo=UTC),
        ),
    )
    recorder.record(
        LLMRunRecord(
            run_id="c",
            caller="test",
            provider="llm:codex:test-model",
            duration_ms=500,
            succeeded=True,
            started_at=datetime(2026, 4, 3, tzinfo=UTC),
        ),
    )


_NO_SESSION_PROBE = AuthTestResult(
    provider="",
    configured=False,
    persisted_session_present=False,
    persisted_session_expired=None,
    persisted_session_state="no_session",
    probe_summary="no provider configured",
)

_STALE_SESSION_PROBE = AuthTestResult(
    provider="certificate",
    configured=True,
    persisted_session_present=True,
    persisted_session_expired=True,
    persisted_session_state="expired",
    probe_summary="session expired",
)


def test_build_run_health_report_folds_llm_runs_and_no_session_probe(profile: TestRuntimeProfile) -> None:
    """Real LLM run records fold per-provider; an injected no-session probe is reported."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.aeat_llm_run_telemetry_dir)
    _seed(recorder)

    report = build_run_health_report(run_telemetry_recorder=recorder, auth_probe=_NO_SESSION_PROBE)

    assert report.has_run_data is True
    providers = {row.provider: row for row in report.llm_providers}
    assert set(providers) == {"llm:claude:test-model", "llm:codex:test-model"}

    claude = providers["llm:claude:test-model"]
    assert claude.runs == 2
    assert claude.succeeded == 1
    assert claude.failed == 1
    assert claude.min_duration_ms == 1000
    assert claude.max_duration_ms == 9000

    assert report.total_runs == 3
    assert report.total_succeeded == 2
    assert report.total_failed == 1

    assert report.auth_configured is False
    assert report.persisted_session_present is False
    assert report.session_stale is False


def test_build_run_health_report_flags_stale_session(profile: TestRuntimeProfile) -> None:
    """An injected expired-session probe is surfaced as ``session_stale``."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.aeat_llm_run_telemetry_dir)

    report = build_run_health_report(run_telemetry_recorder=recorder, auth_probe=_STALE_SESSION_PROBE)

    assert report.has_run_data is False
    assert report.auth_configured is True
    assert report.persisted_session_present is True
    assert report.persisted_session_expired is True
    assert report.session_stale is True


def test_build_run_health_report_provider_filter_scopes_llm_section(profile: TestRuntimeProfile) -> None:
    """The ``provider`` filter restricts only the LLM run-timing section, never the auth probe."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.aeat_llm_run_telemetry_dir)
    _seed(recorder)

    report = build_run_health_report(
        provider="llm:codex:test-model",
        run_telemetry_recorder=recorder,
        auth_probe=_STALE_SESSION_PROBE,
    )

    assert len(report.llm_providers) == 1
    assert report.llm_providers[0].provider == "llm:codex:test-model"
    assert report.total_runs == 1
    # The auth section is unaffected by the LLM provider filter.
    assert report.auth_configured is True
    assert report.session_stale is True


def test_build_run_health_report_date_range_scopes_llm_section(profile: TestRuntimeProfile) -> None:
    """``since``/``until`` narrow the LLM run-timing section by date."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.aeat_llm_run_telemetry_dir)
    _seed(recorder)

    report = build_run_health_report(
        since=date(2026, 4, 1),
        until=date(2026, 4, 1),
        run_telemetry_recorder=recorder,
        auth_probe=_NO_SESSION_PROBE,
    )

    assert report.total_runs == 1
    assert report.llm_providers[0].provider == "llm:claude:test-model"
    assert report.llm_providers[0].runs == 1


def test_build_run_health_report_empty_store_reports_no_run_data(profile: TestRuntimeProfile) -> None:
    """An empty run-telemetry store reports ``has_run_data = False``, not an error."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.aeat_llm_run_telemetry_dir)

    report = build_run_health_report(run_telemetry_recorder=recorder, auth_probe=_NO_SESSION_PROBE)

    assert report.has_run_data is False
    assert report.llm_providers == ()
    assert report.total_runs == 0


def test_list_recent_runs_orders_most_recent_first(profile: TestRuntimeProfile) -> None:
    """Individual run records project most-recent-first, reusing the shared recorder."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.aeat_llm_run_telemetry_dir)
    _seed(recorder)

    rows = list_recent_runs(run_telemetry_recorder=recorder)

    assert [row.run_id for row in rows] == ["c", "b", "a"]
    assert rows[0].provider == "llm:codex:test-model"
    assert rows[0].succeeded is True
    assert rows[1].provider == "llm:claude:test-model"
    assert rows[1].succeeded is False
    assert rows[1].error_kind == "LLMClassifierError"


def test_list_recent_runs_limit_caps_the_most_recent_rows(profile: TestRuntimeProfile) -> None:
    """``limit`` caps the listing to the N most-recent rows, not an arbitrary slice."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.aeat_llm_run_telemetry_dir)
    _seed(recorder)

    rows = list_recent_runs(run_telemetry_recorder=recorder, limit=2)

    assert [row.run_id for row in rows] == ["c", "b"]


def test_list_recent_runs_provider_filter_scopes_the_listing(profile: TestRuntimeProfile) -> None:
    """``provider`` restricts the listing to one provider label."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.aeat_llm_run_telemetry_dir)
    _seed(recorder)

    rows = list_recent_runs(run_telemetry_recorder=recorder, provider="llm:claude:test-model")

    assert {row.run_id for row in rows} == {"a", "b"}
    assert all(row.provider == "llm:claude:test-model" for row in rows)


def test_list_recent_runs_date_range_scopes_the_listing(profile: TestRuntimeProfile) -> None:
    """``since``/``until`` narrow the listing by date, mirroring the recorder's own bound."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.aeat_llm_run_telemetry_dir)
    _seed(recorder)

    rows = list_recent_runs(run_telemetry_recorder=recorder, since=date(2026, 4, 1), until=date(2026, 4, 1))

    assert [row.run_id for row in rows] == ["a"]


def test_list_recent_runs_empty_store_returns_empty_tuple(profile: TestRuntimeProfile) -> None:
    """An empty run-telemetry store returns an empty listing, not an error."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.aeat_llm_run_telemetry_dir)

    rows = list_recent_runs(run_telemetry_recorder=recorder)

    assert rows == ()
