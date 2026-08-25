"""Real-behavior diagnostics over encrypted LLM telemetry and local auth state."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ...adapters.outbound.llm import LLMRunRecord, LLMRunTelemetryRecorder
from ...core import scan_directory
from ...tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ..diagnostics_run_health import (
    ErrorsBreakdownReport,
    LatencyReport,
    LlmRunHealthProviderMetrics,
    LlmUsageReport,
    RunHealthReport,
    build_error_breakdown,
    build_latency_report,
    build_llm_usage_report,
    build_run_health_report,
    list_recent_runs,
)
from ..ledger.llm_diagnostics import LlmUsageCostProviderMetrics

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


def test_build_run_health_report_folds_llm_runs_and_real_auth_probe(profile: TestRuntimeProfile) -> None:
    """Real LLM records fold per provider alongside the real local auth probe."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    _seed(recorder)

    report = build_run_health_report(run_telemetry_recorder=recorder)

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


def test_build_run_health_report_provider_filter_scopes_llm_section(profile: TestRuntimeProfile) -> None:
    """The ``provider`` filter restricts only the LLM run-timing section, never the auth probe."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    _seed(recorder)

    report = build_run_health_report(
        provider="llm:codex:test-model",
        run_telemetry_recorder=recorder,
    )

    assert len(report.llm_providers) == 1
    assert report.llm_providers[0].provider == "llm:codex:test-model"
    assert report.total_runs == 1
    # The auth section is unaffected by the LLM provider filter.
    assert report.auth_configured is False
    assert report.session_stale is False


def test_build_run_health_report_date_range_scopes_llm_section(profile: TestRuntimeProfile) -> None:
    """``since``/``until`` narrow the LLM run-timing section by date."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    _seed(recorder)

    report = build_run_health_report(
        since=date(2026, 4, 1),
        until=date(2026, 4, 1),
        run_telemetry_recorder=recorder,
    )

    assert report.total_runs == 1
    assert report.llm_providers[0].provider == "llm:claude:test-model"
    assert report.llm_providers[0].runs == 1


def test_build_run_health_report_empty_store_reports_no_run_data(profile: TestRuntimeProfile) -> None:
    """An empty run-telemetry store reports ``has_run_data = False``, not an error."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)

    report = build_run_health_report(run_telemetry_recorder=recorder)

    assert report.has_run_data is False
    assert report.llm_providers == ()
    assert report.total_runs == 0


def test_list_recent_runs_orders_most_recent_first(profile: TestRuntimeProfile) -> None:
    """Individual run records project most-recent-first, reusing the shared recorder."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
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
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    _seed(recorder)

    rows = list_recent_runs(run_telemetry_recorder=recorder, limit=2)

    assert [row.run_id for row in rows] == ["c", "b"]


def test_list_recent_runs_provider_filter_scopes_the_listing(profile: TestRuntimeProfile) -> None:
    """``provider`` restricts the listing to one provider label."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    _seed(recorder)

    rows = list_recent_runs(run_telemetry_recorder=recorder, provider="llm:claude:test-model")

    assert {row.run_id for row in rows} == {"a", "b"}
    assert all(row.provider == "llm:claude:test-model" for row in rows)


def test_list_recent_runs_date_range_scopes_the_listing(profile: TestRuntimeProfile) -> None:
    """``since``/``until`` narrow the listing by date, mirroring the recorder's own bound."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    _seed(recorder)

    rows = list_recent_runs(run_telemetry_recorder=recorder, since=date(2026, 4, 1), until=date(2026, 4, 1))

    assert [row.run_id for row in rows] == ["a"]


def test_list_recent_runs_empty_store_returns_empty_tuple(profile: TestRuntimeProfile) -> None:
    """An empty run-telemetry store returns an empty listing, not an error."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)

    rows = list_recent_runs(run_telemetry_recorder=recorder)

    assert rows == ()


def _seed_percentiles(recorder: LLMRunTelemetryRecorder) -> None:
    """Write ten real claude runs with known ascending durations 100..1000ms.

    Nearest-rank percentiles over this exact ten-value ascending set are
    hand-verifiable against the documented method
    (``rank = ceil(percentile * n / 100)``, 1-indexed):
    P50 -> rank 5 -> 500ms; P95 -> rank 10 -> 1000ms; P99 -> rank 10 -> 1000ms.
    """
    for index, duration_ms in enumerate((100, 200, 300, 400, 500, 600, 700, 800, 900, 1000), start=1):
        recorder.record(
            LLMRunRecord(
                run_id=f"lat-{index}",
                caller="test",
                provider="llm:claude:test-model",
                duration_ms=duration_ms,
                succeeded=True,
                started_at=datetime(2026, 5, index, tzinfo=UTC),
            ),
        )


def test_build_latency_report_computes_nearest_rank_percentiles(profile: TestRuntimeProfile) -> None:
    """P50/P95/P99 match the documented nearest-rank method over ten known durations."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    _seed_percentiles(recorder)

    report = build_latency_report(run_telemetry_recorder=recorder)

    assert report.has_run_data is True
    assert report.overall.entries == 10
    assert report.overall.min_duration_ms == 100
    assert report.overall.max_duration_ms == 1000
    assert report.overall.mean_duration_ms == Decimal("550.00")
    assert report.overall.p50_duration_ms == 500
    assert report.overall.p95_duration_ms == 1000
    assert report.overall.p99_duration_ms == 1000


def test_build_latency_report_breaks_down_by_provider(profile: TestRuntimeProfile) -> None:
    """``by_provider`` carries a percentile row per distinct provider when unscoped."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    _seed(recorder)

    report = build_latency_report(run_telemetry_recorder=recorder)

    by_provider = dict(report.by_provider)
    assert set(by_provider) == {"llm:claude:test-model", "llm:codex:test-model"}
    assert by_provider["llm:claude:test-model"].entries == 2
    assert by_provider["llm:codex:test-model"].entries == 1
    assert by_provider["llm:codex:test-model"].p50_duration_ms == 500


def test_build_latency_report_provider_filter_omits_by_provider_breakdown(profile: TestRuntimeProfile) -> None:
    """Scoping to one ``provider`` leaves ``by_provider`` empty (it would duplicate ``overall``)."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    _seed(recorder)

    report = build_latency_report(provider="llm:codex:test-model", run_telemetry_recorder=recorder)

    assert report.overall.entries == 1
    assert report.overall.p50_duration_ms == 500
    assert report.by_provider == ()


def test_build_latency_report_empty_store_reports_no_run_data(profile: TestRuntimeProfile) -> None:
    """An empty run-telemetry store reports ``has_run_data = False``, not an error."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)

    report = build_latency_report(run_telemetry_recorder=recorder)

    assert report.has_run_data is False
    assert report.overall.entries == 0
    assert report.overall.p50_duration_ms is None
    assert report.by_provider == ()


def test_build_latency_report_date_range_scopes_the_percentiles(profile: TestRuntimeProfile) -> None:
    """``since``/``until`` narrow the percentile computation by date."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    _seed(recorder)

    report = build_latency_report(since=date(2026, 4, 1), until=date(2026, 4, 1), run_telemetry_recorder=recorder)

    assert report.overall.entries == 1
    assert report.overall.p50_duration_ms == 1000


def test_build_error_breakdown_groups_by_provider_and_error_kind(profile: TestRuntimeProfile) -> None:
    """Failed runs are grouped by ``(provider, error_kind)`` with a count each."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    _seed(recorder)

    report = build_error_breakdown(run_telemetry_recorder=recorder)

    assert report.has_failures is True
    assert report.total_runs == 3
    assert report.total_failed == 1
    assert len(report.by_error_kind) == 1
    row = report.by_error_kind[0]
    assert row.provider == "llm:claude:test-model"
    assert row.error_kind == "LLMClassifierError"
    assert row.count == 1


def test_build_error_breakdown_sorts_by_descending_count(profile: TestRuntimeProfile) -> None:
    """Rows sort by descending failure count, then provider, then error kind."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    # Two claude failures of kind A, one claude failure of kind B, one codex failure of kind A.
    for index, (provider, error_kind) in enumerate(
        (
            ("llm:claude:test-model", "KindA"),
            ("llm:claude:test-model", "KindA"),
            ("llm:claude:test-model", "KindB"),
            ("llm:codex:test-model", "KindA"),
        ),
        start=1,
    ):
        recorder.record(
            LLMRunRecord(
                run_id=f"err-{index}",
                caller="test",
                provider=provider,
                duration_ms=100,
                succeeded=False,
                error_kind=error_kind,
                started_at=datetime(2026, 5, index, tzinfo=UTC),
            ),
        )

    report = build_error_breakdown(run_telemetry_recorder=recorder)

    assert report.total_failed == 4
    assert [(row.provider, row.error_kind, row.count) for row in report.by_error_kind] == [
        ("llm:claude:test-model", "KindA", 2),
        ("llm:claude:test-model", "KindB", 1),
        ("llm:codex:test-model", "KindA", 1),
    ]


def test_build_error_breakdown_provider_filter_scopes_the_breakdown(profile: TestRuntimeProfile) -> None:
    """``provider`` restricts the breakdown to one provider's failures."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    _seed(recorder)

    report = build_error_breakdown(provider="llm:codex:test-model", run_telemetry_recorder=recorder)

    assert report.total_runs == 1
    assert report.total_failed == 0
    assert report.has_failures is False
    assert report.by_error_kind == ()


def test_build_error_breakdown_empty_store_reports_no_failures(profile: TestRuntimeProfile) -> None:
    """An empty run-telemetry store reports no failures, not an error."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)

    report = build_error_breakdown(run_telemetry_recorder=recorder)

    assert report.has_failures is False
    assert report.total_runs == 0
    assert report.total_failed == 0
    assert report.by_error_kind == ()


def test_build_error_breakdown_succeeded_only_reports_no_failures(profile: TestRuntimeProfile) -> None:
    """A store with only succeeded runs reports zero failures with real recorded runs."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    _seed_percentiles(recorder)

    report = build_error_breakdown(run_telemetry_recorder=recorder)

    assert report.total_runs == 10
    assert report.total_failed == 0
    assert report.has_failures is False
    assert report.by_error_kind == ()


def _seed_usage(recorder: LLMRunTelemetryRecorder) -> None:
    """Write six real run-timing records across two providers and three models.

    ``llm:claude:test-model`` uses ``model-a`` (two succeeded: 100ms, 300ms)
    and ``model-b`` (one succeeded 200ms, one failed 400ms);
    ``llm:codex:test-model`` uses only ``model-a`` (two succeeded: 50ms,
    150ms). This exercises both the provider-level fold and the nested
    per-model fold within a provider using more than one model.
    """
    seeds = (
        ("u-1", "llm:claude:test-model", "model-a", 100, True, ""),
        ("u-2", "llm:claude:test-model", "model-a", 300, True, ""),
        ("u-3", "llm:claude:test-model", "model-b", 200, True, ""),
        ("u-4", "llm:claude:test-model", "model-b", 400, False, "LLMClassifierError"),
        ("u-5", "llm:codex:test-model", "model-a", 50, True, ""),
        ("u-6", "llm:codex:test-model", "model-a", 150, True, ""),
    )
    for index, (run_id, provider, model, duration_ms, succeeded, error_kind) in enumerate(seeds, start=1):
        recorder.record(
            LLMRunRecord(
                run_id=run_id,
                caller="test",
                provider=provider,
                model=model,
                duration_ms=duration_ms,
                succeeded=succeeded,
                error_kind=error_kind,
                started_at=datetime(2026, 6, index, tzinfo=UTC),
            ),
        )


def test_build_llm_usage_report_aggregates_by_provider_and_model(profile: TestRuntimeProfile) -> None:
    """Real recorded runs fold per-provider, and per-model within each provider."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    _seed_usage(recorder)

    report = build_llm_usage_report(run_telemetry_recorder=recorder)

    assert report.has_run_data is True
    assert report.total_runs == 6
    assert report.total_succeeded == 5
    assert report.total_failed == 1
    assert report.overall_success_rate == Decimal("0.8333")

    providers = {row.provider: row for row in report.by_provider}
    assert set(providers) == {"llm:claude:test-model", "llm:codex:test-model"}

    claude = providers["llm:claude:test-model"]
    assert claude.runs == 4
    assert claude.succeeded == 3
    assert claude.failed == 1
    assert claude.min_duration_ms == 100
    assert claude.max_duration_ms == 400
    assert claude.total_duration_ms == 1000
    assert claude.success_rate == Decimal("0.7500")

    claude_models = {row.model: row for row in claude.models}
    assert set(claude_models) == {"model-a", "model-b"}
    assert claude_models["model-a"].runs == 2
    assert claude_models["model-a"].succeeded == 2
    assert claude_models["model-a"].total_duration_ms == 400
    assert claude_models["model-a"].success_rate == Decimal("1.0000")
    assert claude_models["model-b"].runs == 2
    assert claude_models["model-b"].succeeded == 1
    assert claude_models["model-b"].failed == 1
    assert claude_models["model-b"].success_rate == Decimal("0.5000")

    codex = providers["llm:codex:test-model"]
    assert codex.runs == 2
    assert codex.succeeded == 2
    assert codex.failed == 0
    assert len(codex.models) == 1
    assert codex.models[0].model == "model-a"
    assert codex.models[0].runs == 2


def test_build_llm_usage_report_provider_filter_scopes_the_summary(profile: TestRuntimeProfile) -> None:
    """``provider`` restricts the summary to one provider's runs."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    _seed_usage(recorder)

    report = build_llm_usage_report(provider="llm:codex:test-model", run_telemetry_recorder=recorder)

    assert len(report.by_provider) == 1
    assert report.by_provider[0].provider == "llm:codex:test-model"
    assert report.total_runs == 2
    assert report.total_succeeded == 2
    assert report.total_failed == 0


def test_build_llm_usage_report_date_range_scopes_the_summary(profile: TestRuntimeProfile) -> None:
    """``since``/``until`` narrow the usage summary by date."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    _seed_usage(recorder)

    report = build_llm_usage_report(since=date(2026, 6, 1), until=date(2026, 6, 1), run_telemetry_recorder=recorder)

    assert report.total_runs == 1
    assert len(report.by_provider) == 1
    assert report.by_provider[0].provider == "llm:claude:test-model"
    assert report.by_provider[0].models[0].model == "model-a"


def test_build_llm_usage_report_empty_store_reports_no_run_data(profile: TestRuntimeProfile) -> None:
    """An empty run-telemetry store reports ``has_run_data = False``, not an error."""
    recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)

    report = build_llm_usage_report(run_telemetry_recorder=recorder)

    assert report.has_run_data is False
    assert report.by_provider == ()
    assert report.total_runs == 0
    assert report.overall_success_rate == Decimal("0")


def test_llm_provider_metric_authorities_have_no_retired_or_split_public_identity() -> None:
    """The two providers' metric shapes retain distinct canonical homes."""
    assert LlmRunHealthProviderMetrics.__module__ == "cadrumo.application.diagnostics_run_health"
    assert LlmUsageCostProviderMetrics.__module__ == "cadrumo.application.ledger.llm_diagnostics"

    source_root = Path(__file__).parents[2]
    owners = {
        "LlmRunHealthProviderMetrics": Path("application/diagnostics_run_health.py"),
        "LlmUsageCostProviderMetrics": Path("application/ledger/llm_diagnostics.py"),
    }
    retired_public_name = "LlmUsage" + "ProviderMetrics"
    declarations: dict[str, set[Path]] = {name: set() for name in owners}
    for source_path in scan_directory(source_root, pattern="*.py", recursive=True):
        source = source_path.read_text(encoding="utf-8")
        assert retired_public_name not in source
        for node in ast.walk(ast.parse(source, filename=str(source_path))):
            if isinstance(node, ast.ClassDef) and node.name in declarations:
                declarations[node.name].add(source_path.relative_to(source_root))

    for name, owner in owners.items():
        assert declarations[name] == {owner}


class TestReportWindowInvariant:
    """No diagnostics report can present a window that cannot contain a run.

    ``--since`` and ``--until`` are parsed independently at the CLI, so neither
    parse site can see the other's value. A reversed pair matches no record and
    the report renders a window that never existed while claiming zero
    observations — indistinguishable from a genuinely quiet period. Every
    report carries the one canonical invariant.
    """

    _REPORTS = (
        RunHealthReport,
        LatencyReport,
        ErrorsBreakdownReport,
        LlmUsageReport,
    )

    @pytest.mark.parametrize("report", _REPORTS)
    def test_reversed_window_is_refused(self, report: type) -> None:
        with pytest.raises(ValidationError):
            report(since=date(2026, 2, 1), until=date(2026, 1, 1))

    @pytest.mark.parametrize("report", _REPORTS)
    def test_ordered_window_is_accepted(self, report: type) -> None:
        built = report(since=date(2026, 1, 1), until=date(2026, 2, 1))
        assert built.since == date(2026, 1, 1)
        assert built.until == date(2026, 2, 1)

    @pytest.mark.parametrize("report", _REPORTS)
    def test_single_day_window_is_accepted(self, report: type) -> None:
        """Equal bounds are a legitimate one-day query, not an empty interval."""
        assert report(since=date(2026, 1, 1), until=date(2026, 1, 1)).until == date(2026, 1, 1)

    @pytest.mark.parametrize("report", _REPORTS)
    def test_open_and_absent_bounds_stay_permitted(self, report: type) -> None:
        """The invariant must not turn an optional bound into a required one."""
        assert report().since is None
        assert report(since=date(2026, 1, 1)).until is None
        assert report(until=date(2026, 2, 1)).since is None


def test_builders_refuse_a_reversed_window(profile: TestRuntimeProfile) -> None:
    """The refusal reaches the real builders, not only direct construction."""
    recorder = LLMRunTelemetryRecorder()
    _seed(recorder)
    for build in (build_run_health_report, build_latency_report, build_error_breakdown, build_llm_usage_report):
        with pytest.raises(ValidationError):
            build(since=date(2026, 2, 1), until=date(2026, 1, 1))
