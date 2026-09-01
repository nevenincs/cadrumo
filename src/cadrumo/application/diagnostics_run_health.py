"""Local-only run-health diagnostics: LLM run timing plus auth-session staleness.

Folds two existing local-only signals into one typed operator-facing report so
a slow LLM-backed classification run or a stale/expired persisted AEAT auth
session is diagnosable without leaving the host:

* :class:`~adapters.outbound.llm.LLMRunTelemetryRecorder` records
  duration/outcome metadata for every LLM classification, split-proposal, and
  completion run (see :class:`~llm.LLMClient` and
  :mod:`~application.ledger.llm_classification`); and
* :func:`~application.auth.test_operator_auth` reports whether an
  encrypted AEAT session token is present on disk and whether it has passed
  its idle deadline.

Nothing here performs a network call or a live AEAT read: the LLM run records
are read from encrypted local secure-object storage and the auth probe reads
only the locally persisted session token's metadata. This backs the
``aeat app diagnostics run-health`` operator surface.

:func:`list_recent_runs` projects the same recorded :class:`LLMRunRecord` rows
individually (most-recent-first, optionally limited) rather than aggregated
per-provider, backing the sibling ``aeat app diagnostics runs`` listing verb.
It reuses
:meth:`~adapters.outbound.llm.LLMRunTelemetryRecorder.load_records`
directly -- there is no parallel capture or storage path here.

:func:`build_latency_report` and :func:`build_error_breakdown` project the
*same* recorded rows into a percentile-latency view and a failed-run
error-kind breakdown, backing the ``aeat app diagnostics latency`` and
``aeat app diagnostics errors`` verbs. Neither
introduces a new capture or storage path -- both read
:meth:`~adapters.outbound.llm.LLMRunTelemetryRecorder.load_records`
exactly as ``run-health`` and ``runs`` do, honouring
``aeat-architecture-boundaries``.

:func:`build_llm_usage_report` projects the same recorded rows into a
run-count/duration/success-rate summary grouped by provider AND by model,
backing the ``aeat app diagnostics llm-usage`` verb.
:class:`~adapters.outbound.llm.LLMRunRecord` carries only timing and
outcome metadata -- no token counts are recorded on this store -- so the
usage summary reports run counts, durations, and success rate rather than
token/cost figures (those are covered by the separate
:func:`~application.ledger.llm_diagnostics.build_llm_diagnostics_report`
usage/cost/confidence report, which folds the distinct completion-call
:class:`~llm.UsageRecord` log). This report again
reuses :meth:`~adapters.outbound.llm.LLMRunTelemetryRecorder.load_records`
directly -- there is no parallel capture or storage path here either.

See Also:
    :class:`~adapters.outbound.llm.LLMRunTelemetryRecorder`
        Local encrypted recorder that supplies every run row this module reads.
    :class:`~adapters.outbound.llm.LLMRunRecord`
        Timing/outcome-only record projected into each diagnostic report.
    :func:`~application.auth.test_operator_auth`
        Local auth-session probe folded into the run-health report.
    :mod:`~entrypoints.cli._app_diagnostics`
        CLI transport for the run-health, runs, latency, errors, and
        llm-usage verbs.
    :mod:`~application.diagnostics_telemetry`
        Remote-telemetry posture/flush service that reuses the aggregate
        LLM-run signal without widening the payload.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, model_validator

from ..adapters.outbound.llm.run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder
from ..core.time.date_range import validate_inclusive_date_range
from .auth.operator import test_operator_auth

__all__ = [
    "ErrorKindCount",
    "ErrorsBreakdownReport",
    "LatencyPercentiles",
    "LatencyReport",
    "LlmRunHealthProviderMetrics",
    "LlmRunProviderMetrics",
    "LlmUsageModelMetrics",
    "LlmUsageReport",
    "RunHealthReport",
    "RunRecordView",
    "build_error_breakdown",
    "build_latency_report",
    "build_llm_usage_report",
    "build_run_health_report",
    "list_recent_runs",
]



class _RunTimingMetrics(TypedDict):
    """Canonical aggregate facts shared by every run-timing projection."""

    runs: int
    succeeded: int
    failed: int
    min_duration_ms: int
    max_duration_ms: int
    mean_duration_ms: Decimal


def _run_timing_metrics(items: list[LLMRunRecord]) -> _RunTimingMetrics:
    """Fold one non-empty group of run records into shared timing facts."""
    durations = [Decimal(item.duration_ms) for item in items]
    return {
        "runs": len(items),
        "succeeded": sum(1 for item in items if item.succeeded),
        "failed": sum(1 for item in items if not item.succeeded),
        "min_duration_ms": min(item.duration_ms for item in items),
        "max_duration_ms": max(item.duration_ms for item in items),
        "mean_duration_ms": (sum(durations, start=Decimal("0")) / Decimal(len(durations))).quantize(
            Decimal("0.01"),
        ),
    }


#: Deliberately NOT the canonical ``STRICT_FROZEN_CONFIG``: the records below are
#: ``RootModel`` subclasses, and pydantic refuses ``extra`` on a root model
#: outright -- ``PydanticUserError: RootModel does not support setting
#: model_config['extra']``. The canonical config carries ``extra="forbid"``, so it
#: cannot be applied here at all. This is a constraint-shape divergence, not a
#: weaker config nobody chose.
_STRICT_FROZEN = ConfigDict(strict=True, frozen=True)


class LlmRunProviderMetrics(BaseModel):
    """Per-provider aggregate of recent local LLM run-timing telemetry.

    Aggregated from :class:`~adapters.outbound.llm.LLMRunRecord` rows for
    a single :attr:`provider`. Carries only timing and outcome metadata --
    never prompt or response text.
    """

    model_config = _STRICT_FROZEN

    provider: str = Field(min_length=1)
    runs: NonNegativeInt
    succeeded: NonNegativeInt
    failed: NonNegativeInt
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    mean_duration_ms: Decimal | None = None


class RunHealthReport(BaseModel):
    """Typed local-only run-health report: LLM run timing plus auth staleness.

    Produced by :func:`build_run_health_report`. :attr:`has_run_data` is
    ``False`` when no LLM run telemetry has been recorded yet, so callers can
    print an instructive empty message. The auth section always carries a
    verdict (a fresh profile with no configured provider still reports
    ``persisted_session_present = False``).
    """

    model_config = _STRICT_FROZEN

    since: date | None = None
    until: date | None = None
    llm_providers: tuple[LlmRunProviderMetrics, ...] = ()
    total_runs: int = Field(default=0, ge=0)
    total_succeeded: int = Field(default=0, ge=0)
    total_failed: int = Field(default=0, ge=0)
    auth_provider: str = ""
    auth_configured: bool = False
    persisted_session_present: bool = False
    persisted_session_expired: bool | None = None
    persisted_session_state: str = ""
    probe_summary: str = ""

    @model_validator(mode="after")
    def _window_is_not_empty(self) -> RunHealthReport:
        """Reject a reported window whose ``until`` precedes its ``since``.

        The two bounds are parsed independently at the CLI, so neither
        parse site can see the other. A reversed pair renders a window
        that never existed while reporting zero observations, which reads
        exactly like a real quiet period.
        """
        validate_inclusive_date_range(self.since, self.until)
        return self

    @property
    def has_run_data(self) -> bool:
        """Return ``True`` when at least one LLM run has been recorded locally."""
        return bool(self.llm_providers)

    @property
    def session_stale(self) -> bool:
        """Return ``True`` when a persisted session exists and has expired."""
        return self.persisted_session_present and bool(self.persisted_session_expired)


def build_run_health_report(
    *,
    since: date | None = None,
    until: date | None = None,
    provider: str | None = None,
    run_telemetry_recorder: LLMRunTelemetryRecorder | None = None,
) -> RunHealthReport:
    """Aggregate local LLM run telemetry and the auth-session probe into one report.

    Args:
        since: Inclusive lower date bound on run records, or ``None``.
        until: Inclusive upper date bound on run records, or ``None``.
        provider: Optional LLM run-record provider label filter (e.g.
            ``"llm:claude:sonnet"``, ``"claude"``); scopes ONLY the LLM
            run-timing section. This is distinct from an AEAT auth provider
            name -- the auth-session probe always auto-resolves its provider
            from workflow state and never receives this filter.
        run_telemetry_recorder: Injected recorder (dependency injection for
            tests); defaults to the active-bucket
            :class:`~adapters.outbound.llm.LLMRunTelemetryRecorder`.

    Returns:
        The populated :class:`RunHealthReport`.
    """
    recorder = run_telemetry_recorder or LLMRunTelemetryRecorder()
    records = recorder.load_records(since=since, until=until)
    if provider is not None:
        records = tuple(item for item in records if item.provider == provider)
    llm_providers = _aggregate_runs(records)

    probe = test_operator_auth()

    return RunHealthReport(
        since=since,
        until=until,
        llm_providers=llm_providers,
        total_runs=sum(row.runs for row in llm_providers),
        total_succeeded=sum(row.succeeded for row in llm_providers),
        total_failed=sum(row.failed for row in llm_providers),
        auth_provider=probe.provider,
        auth_configured=probe.configured,
        persisted_session_present=probe.persisted_session_present,
        persisted_session_expired=probe.persisted_session_expired,
        persisted_session_state=probe.persisted_session_state,
        probe_summary=probe.probe_summary,
    )


class RunRecordView(BaseModel):
    """One individual local LLM run-timing record, as reported to an operator.

    Mirrors :class:`~adapters.outbound.llm.LLMRunRecord` field-for-field;
    carries only accounting/timing metadata, never prompt or response text.
    """

    model_config = _STRICT_FROZEN

    run_id: str = Field(min_length=1)
    caller: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = ""
    duration_ms: NonNegativeInt
    succeeded: bool
    error_kind: str = ""
    started_at: datetime


def list_recent_runs(
    *,
    since: date | None = None,
    until: date | None = None,
    provider: str | None = None,
    limit: int | None = None,
    run_telemetry_recorder: LLMRunTelemetryRecorder | None = None,
) -> tuple[RunRecordView, ...]:
    """Return recent local LLM run-timing records, most-recent-first.

    Reuses :meth:`~adapters.outbound.llm.LLMRunTelemetryRecorder.load_records`
    directly -- the same recorder :func:`build_run_health_report` reads -- so
    there is no parallel capture or storage path for this listing.

    Args:
        since: Inclusive lower date bound on run records, or ``None``.
        until: Inclusive upper date bound on run records, or ``None``.
        provider: Optional provider label filter; ``None`` returns every
            provider.
        limit: Optional cap on the number of most-recent rows returned;
            ``None`` returns every matching record.
        run_telemetry_recorder: Injected recorder (dependency injection for
            tests); defaults to the active-bucket
            :class:`~adapters.outbound.llm.LLMRunTelemetryRecorder`.

    Returns:
        Matching :class:`RunRecordView` rows ordered most-recent-first (ties
        broken by ``run_id`` descending, mirroring the recorder's own stable
        ascending order reversed).
    """
    recorder = run_telemetry_recorder or LLMRunTelemetryRecorder()
    records = recorder.load_records(since=since, until=until)
    if provider is not None:
        records = tuple(item for item in records if item.provider == provider)
    ordered = tuple(reversed(records))
    if limit is not None:
        ordered = ordered[:limit]
    return tuple(
        RunRecordView(
            run_id=item.run_id,
            caller=item.caller,
            provider=item.provider,
            model=item.model,
            duration_ms=item.duration_ms,
            succeeded=item.succeeded,
            error_kind=item.error_kind,
            started_at=item.started_at,
        )
        for item in ordered
    )


class LatencyPercentiles(BaseModel):
    """Percentile and summary latency statistics over a set of run durations.

    Percentiles are computed with the nearest-rank method (ceil(p * n / 100),
    1-indexed into the ascending-sorted duration list) -- a deterministic,
    interpolation-free method whose outputs always equal a recorded duration
    value. Populated only when at least one duration is present; ``entries``
    is ``0`` (all other fields absent) for an empty input.
    """

    model_config = _STRICT_FROZEN

    entries: int = Field(default=0, ge=0)
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    mean_duration_ms: Decimal | None = None
    p50_duration_ms: int | None = None
    p95_duration_ms: int | None = None
    p99_duration_ms: int | None = None


class LatencyReport(BaseModel):
    """Typed local-only latency report: overall plus optional per-provider percentiles.

    Produced by :func:`build_latency_report`. :attr:`by_provider` is populated
    only when the caller did not scope the query to a single ``provider``
    filter (a single-provider query makes :attr:`overall` and the sole
    provider row redundant).
    """

    model_config = _STRICT_FROZEN

    since: date | None = None
    until: date | None = None
    provider: str | None = None
    overall: LatencyPercentiles = Field(default_factory=LatencyPercentiles)
    by_provider: tuple[tuple[str, LatencyPercentiles], ...] = ()

    @model_validator(mode="after")
    def _window_is_not_empty(self) -> LatencyReport:
        """Reject a reported window whose ``until`` precedes its ``since``.

        The two bounds are parsed independently at the CLI, so neither
        parse site can see the other. A reversed pair renders a window
        that never existed while reporting zero observations, which reads
        exactly like a real quiet period.
        """
        validate_inclusive_date_range(self.since, self.until)
        return self

    @property
    def has_run_data(self) -> bool:
        """Return ``True`` when at least one run duration was aggregated."""
        return self.overall.entries > 0


class ErrorKindCount(BaseModel):
    """One ``error_kind`` value's failure count, optionally scoped to a provider."""

    model_config = _STRICT_FROZEN

    error_kind: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    count: int = Field(ge=1)


class ErrorsBreakdownReport(BaseModel):
    """Typed local-only breakdown of failed LLM runs by provider and error kind.

    Produced by :func:`build_error_breakdown`. Rows are sorted by descending
    ``count``, then by ``provider``, then by ``error_kind`` for a stable
    presentation order.
    """

    model_config = _STRICT_FROZEN

    since: date | None = None
    until: date | None = None
    provider: str | None = None
    total_runs: int = Field(default=0, ge=0)
    total_failed: int = Field(default=0, ge=0)
    by_error_kind: tuple[ErrorKindCount, ...] = ()

    @model_validator(mode="after")
    def _window_is_not_empty(self) -> ErrorsBreakdownReport:
        """Reject a reported window whose ``until`` precedes its ``since``.

        The two bounds are parsed independently at the CLI, so neither
        parse site can see the other. A reversed pair renders a window
        that never existed while reporting zero observations, which reads
        exactly like a real quiet period.
        """
        validate_inclusive_date_range(self.since, self.until)
        return self

    @property
    def has_failures(self) -> bool:
        """Return ``True`` when at least one failed run was recorded."""
        return self.total_failed > 0


def _percentile(sorted_durations: list[int], percentile: int) -> int:
    """Return the nearest-rank ``percentile`` value from ascending ``sorted_durations``.

    Uses the nearest-rank method: ``rank = ceil(percentile * n / 100)``,
    clamped to ``[1, n]`` and converted to a 0-based index. Deterministic and
    always returns one of the recorded duration values (no interpolation).
    """
    n = len(sorted_durations)
    rank = -(-percentile * n // 100)  # ceil division
    rank = max(1, min(rank, n))
    return sorted_durations[rank - 1]


def _latency_percentiles(records: list[LLMRunRecord]) -> LatencyPercentiles:
    """Compute :class:`LatencyPercentiles` over ``records``' durations."""
    if not records:
        return LatencyPercentiles()
    durations = sorted(item.duration_ms for item in records)
    decimals = [Decimal(value) for value in durations]
    mean = (sum(decimals, start=Decimal("0")) / Decimal(len(decimals))).quantize(Decimal("0.01"))
    return LatencyPercentiles(
        entries=len(durations),
        min_duration_ms=durations[0],
        max_duration_ms=durations[-1],
        mean_duration_ms=mean,
        p50_duration_ms=_percentile(durations, 50),
        p95_duration_ms=_percentile(durations, 95),
        p99_duration_ms=_percentile(durations, 99),
    )


def build_latency_report(
    *,
    since: date | None = None,
    until: date | None = None,
    provider: str | None = None,
    run_telemetry_recorder: LLMRunTelemetryRecorder | None = None,
) -> LatencyReport:
    """Aggregate recorded run durations into overall and per-provider percentiles.

    Reuses :meth:`~adapters.outbound.llm.LLMRunTelemetryRecorder.load_records`
    directly -- the same recorder :func:`build_run_health_report` and
    :func:`list_recent_runs` read -- so there is no parallel capture or
    storage path for this report.

    Args:
        since: Inclusive lower date bound on run records, or ``None``.
        until: Inclusive upper date bound on run records, or ``None``.
        provider: Optional provider label filter; when supplied, ``overall``
            reflects only that provider's runs and ``by_provider`` is left
            empty (a single-provider breakdown would duplicate ``overall``).
        run_telemetry_recorder: Injected recorder (dependency injection for
            tests); defaults to the active-bucket
            :class:`~adapters.outbound.llm.LLMRunTelemetryRecorder`.

    Returns:
        The populated :class:`LatencyReport`.
    """
    recorder = run_telemetry_recorder or LLMRunTelemetryRecorder()
    records = recorder.load_records(since=since, until=until)
    if provider is not None:
        records = tuple(item for item in records if item.provider == provider)

    overall = _latency_percentiles(list(records))

    by_provider: tuple[tuple[str, LatencyPercentiles], ...] = ()
    if provider is None:
        grouped: dict[str, list[LLMRunRecord]] = {}
        for record in records:
            grouped.setdefault(record.provider, []).append(record)
        by_provider = tuple(
            (provider_name, _latency_percentiles(grouped[provider_name])) for provider_name in sorted(grouped)
        )

    return LatencyReport(since=since, until=until, provider=provider, overall=overall, by_provider=by_provider)


def build_error_breakdown(
    *,
    since: date | None = None,
    until: date | None = None,
    provider: str | None = None,
    run_telemetry_recorder: LLMRunTelemetryRecorder | None = None,
) -> ErrorsBreakdownReport:
    """Group failed recorded runs by provider and ``error_kind``.

    Reuses :meth:`~adapters.outbound.llm.LLMRunTelemetryRecorder.load_records`
    directly -- the same recorder every sibling diagnostics report reads --
    so there is no parallel capture or storage path for this report.

    Args:
        since: Inclusive lower date bound on run records, or ``None``.
        until: Inclusive upper date bound on run records, or ``None``.
        provider: Optional provider label filter; ``None`` breaks down every
            provider's failures.
        run_telemetry_recorder: Injected recorder (dependency injection for
            tests); defaults to the active-bucket
            :class:`~adapters.outbound.llm.LLMRunTelemetryRecorder`.

    Returns:
        The populated :class:`ErrorsBreakdownReport`.
    """
    recorder = run_telemetry_recorder or LLMRunTelemetryRecorder()
    records = recorder.load_records(since=since, until=until)
    if provider is not None:
        records = tuple(item for item in records if item.provider == provider)

    failed = [item for item in records if not item.succeeded]
    counts: dict[tuple[str, str], int] = {}
    for item in failed:
        error_kind = item.error_kind or "unknown"
        key = (item.provider, error_kind)
        counts[key] = counts.get(key, 0) + 1

    rows = [
        ErrorKindCount(error_kind=error_kind, provider=provider_name, count=count)
        for (provider_name, error_kind), count in counts.items()
    ]
    rows.sort(key=lambda row: (-row.count, row.provider, row.error_kind))

    return ErrorsBreakdownReport(
        since=since,
        until=until,
        provider=provider,
        total_runs=len(records),
        total_failed=len(failed),
        by_error_kind=tuple(rows),
    )


class LlmUsageModelMetrics(BaseModel):
    """One provider's per-model aggregate of recent local LLM run telemetry.

    Aggregated from :class:`~adapters.outbound.llm.LLMRunRecord` rows
    sharing a single provider (recorded on the owning
    :class:`LlmRunHealthProviderMetrics`) AND :attr:`model`. Carries only
    run-count, duration, and outcome metadata -- :class:`LLMRunRecord` records
    no token counts, so this is a run/timing/success-rate summary, not a
    token-usage summary.
    """

    model_config = _STRICT_FROZEN

    model: str = ""
    runs: NonNegativeInt
    succeeded: NonNegativeInt
    failed: NonNegativeInt
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    mean_duration_ms: Decimal | None = None
    total_duration_ms: int = Field(default=0, ge=0)

    @property
    def success_rate(self) -> Decimal:
        """Return the fraction of runs that succeeded, or ``0`` when ``runs`` is ``0``."""
        if self.runs == 0:
            return Decimal("0")
        return (Decimal(self.succeeded) / Decimal(self.runs)).quantize(Decimal("0.0001"))


class LlmRunHealthProviderMetrics(BaseModel):
    """One provider's aggregate of recent local LLM run telemetry, plus its per-model rows.

    :attr:`models` breaks the same provider-scoped records down further by
    :attr:`~LlmUsageModelMetrics.model`, so an operator can see which model
    within a provider drives run volume, duration, or failures.
    """

    model_config = _STRICT_FROZEN

    provider: str = Field(min_length=1)
    runs: NonNegativeInt
    succeeded: NonNegativeInt
    failed: NonNegativeInt
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    mean_duration_ms: Decimal | None = None
    total_duration_ms: int = Field(default=0, ge=0)
    models: tuple[LlmUsageModelMetrics, ...] = ()

    @property
    def success_rate(self) -> Decimal:
        """Return the fraction of runs that succeeded, or ``0`` when ``runs`` is ``0``."""
        if self.runs == 0:
            return Decimal("0")
        return (Decimal(self.succeeded) / Decimal(self.runs)).quantize(Decimal("0.0001"))


class LlmUsageReport(BaseModel):
    """Typed local-only LLM usage summary: run counts, durations, and success rate.

    Produced by :func:`build_llm_usage_report`. Groups the same recorded
    :class:`~adapters.outbound.llm.LLMRunRecord` rows
    :func:`build_run_health_report` reads by provider (:attr:`by_provider`),
    each provider row carrying its own per-model breakdown
    (:attr:`~LlmRunHealthProviderMetrics.models`). :attr:`has_run_data` is
    ``False`` when no LLM run telemetry has been recorded yet.
    """

    model_config = _STRICT_FROZEN

    since: date | None = None
    until: date | None = None
    by_provider: tuple[LlmRunHealthProviderMetrics, ...] = ()
    total_runs: int = Field(default=0, ge=0)
    total_succeeded: int = Field(default=0, ge=0)
    total_failed: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _window_is_not_empty(self) -> LlmUsageReport:
        """Reject a reported window whose ``until`` precedes its ``since``.

        The two bounds are parsed independently at the CLI, so neither
        parse site can see the other. A reversed pair renders a window
        that never existed while reporting zero observations, which reads
        exactly like a real quiet period.
        """
        validate_inclusive_date_range(self.since, self.until)
        return self

    @property
    def has_run_data(self) -> bool:
        """Return ``True`` when at least one LLM run has been recorded locally."""
        return bool(self.by_provider)

    @property
    def overall_success_rate(self) -> Decimal:
        """Return the fraction of all recorded runs that succeeded, or ``0`` when empty."""
        if self.total_runs == 0:
            return Decimal("0")
        return (Decimal(self.total_succeeded) / Decimal(self.total_runs)).quantize(Decimal("0.0001"))


def _usage_model_metrics(items: list[LLMRunRecord]) -> LlmUsageModelMetrics:
    """Fold ``items`` (already scoped to one provider/model pair) into one metrics row."""
    durations = [Decimal(item.duration_ms) for item in items]
    return LlmUsageModelMetrics(
        model=items[0].model,
        runs=len(items),
        succeeded=sum(1 for item in items if item.succeeded),
        failed=sum(1 for item in items if not item.succeeded),
        min_duration_ms=min(item.duration_ms for item in items),
        max_duration_ms=max(item.duration_ms for item in items),
        mean_duration_ms=(sum(durations, start=Decimal("0")) / Decimal(len(durations))).quantize(Decimal("0.01")),
        total_duration_ms=sum((item.duration_ms for item in items), start=0),
    )


def build_llm_usage_report(
    *,
    since: date | None = None,
    until: date | None = None,
    provider: str | None = None,
    run_telemetry_recorder: LLMRunTelemetryRecorder | None = None,
) -> LlmUsageReport:
    """Aggregate recorded LLM run telemetry into a usage summary by provider and model.

    Reuses :meth:`~adapters.outbound.llm.LLMRunTelemetryRecorder.load_records`
    directly -- the same recorder every sibling diagnostics report reads --
    so there is no parallel capture or storage path for this report
    (``aeat-architecture-boundaries``).
    :class:`~adapters.outbound.llm.LLMRunRecord` carries no token
    counts, so this is a run-count/duration/success-rate summary rather than
    a token-usage summary.

    Args:
        since: Inclusive lower date bound on run records, or ``None``.
        until: Inclusive upper date bound on run records, or ``None``.
        provider: Optional provider label filter; ``None`` aggregates every
            provider.
        run_telemetry_recorder: Injected recorder (dependency injection for
            tests); defaults to the active-bucket
            :class:`~adapters.outbound.llm.LLMRunTelemetryRecorder`.

    Returns:
        The populated :class:`LlmUsageReport`.
    """
    recorder = run_telemetry_recorder or LLMRunTelemetryRecorder()
    records = recorder.load_records(since=since, until=until)
    if provider is not None:
        records = tuple(item for item in records if item.provider == provider)

    by_provider_model: dict[str, dict[str, list[LLMRunRecord]]] = {}
    for record in records:
        by_provider_model.setdefault(record.provider, {}).setdefault(record.model, []).append(record)

    provider_rows: list[LlmRunHealthProviderMetrics] = []
    for provider_name in sorted(by_provider_model):
        model_groups = by_provider_model[provider_name]
        model_rows = tuple(_usage_model_metrics(model_groups[model_name]) for model_name in sorted(model_groups))
        provider_items = [item for items in model_groups.values() for item in items]
        provider_rows.append(
            LlmRunHealthProviderMetrics(
                provider=provider_name,
                **_run_timing_metrics(provider_items),
                total_duration_ms=sum((item.duration_ms for item in provider_items), start=0),
                models=model_rows,
            ),
        )

    return LlmUsageReport(
        since=since,
        until=until,
        by_provider=tuple(provider_rows),
        total_runs=len(records),
        total_succeeded=sum(1 for item in records if item.succeeded),
        total_failed=sum(1 for item in records if not item.succeeded),
    )


def _aggregate_runs(records: tuple[LLMRunRecord, ...]) -> tuple[LlmRunProviderMetrics, ...]:
    """Fold run records into one metrics row per provider, provider-sorted."""
    by_provider: dict[str, list[LLMRunRecord]] = {}
    for record in records:
        by_provider.setdefault(record.provider, []).append(record)
    rows: list[LlmRunProviderMetrics] = []
    for provider_name in sorted(by_provider):
        items = by_provider[provider_name]
        rows.append(
            LlmRunProviderMetrics(
                provider=provider_name,
                **_run_timing_metrics(items),
            ),
        )
    return tuple(rows)
