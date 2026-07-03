"""Local-only run-health diagnostics: LLM run timing plus auth-session staleness.

Folds two existing local-only signals into one typed operator-facing report so
a slow LLM-backed classification run or a stale/expired persisted AEAT auth
session is diagnosable without leaving the host:

* :class:`~aeat.adapters.outbound.llm.LLMRunTelemetryRecorder` records
  duration/outcome metadata for every LLM classification, split-proposal, and
  completion run (see :mod:`aeat.adapters.outbound.llm._client` and
  :mod:`aeat.application.ledger._llm_classification`); and
* :func:`aeat.application.auth.test_operator_auth` reports whether an
  encrypted AEAT session token is present on disk and whether it has passed
  its idle deadline.

Nothing here performs a network call or a live AEAT read: the LLM run records
are read from encrypted local secure-object storage and the auth probe reads
only the locally persisted session token's metadata. This backs the
``aeat app diagnostics run-health`` operator surface (GitHub issue #407).

:func:`list_recent_runs` projects the same recorded :class:`LLMRunRecord` rows
individually (most-recent-first, optionally limited) rather than aggregated
per-provider, backing the sibling ``aeat app diagnostics runs`` listing verb
(also GitHub issue #407). It reuses
:meth:`~aeat.adapters.outbound.llm.LLMRunTelemetryRecorder.load_records`
directly -- there is no parallel capture or storage path here.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ..adapters.outbound.llm import LLMRunRecord, LLMRunTelemetryRecorder
from .auth import AuthTestResult, test_operator_auth

__all__ = [
    "LlmRunProviderMetrics",
    "RunHealthReport",
    "RunRecordView",
    "build_run_health_report",
    "list_recent_runs",
]

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True)


class LlmRunProviderMetrics(BaseModel):
    """Per-provider aggregate of recent local LLM run-timing telemetry.

    Aggregated from :class:`~aeat.adapters.outbound.llm.LLMRunRecord` rows for
    a single :attr:`provider`. Carries only timing and outcome metadata --
    never prompt or response text.
    """

    model_config = _STRICT_FROZEN

    provider: str = Field(min_length=1)
    runs: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
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
    auth_probe: AuthTestResult | None = None,
) -> RunHealthReport:
    """Aggregate local LLM run telemetry and the auth-session probe into one report.

    Args:
        since: Inclusive lower date bound on run records, or ``None``.
        until: Inclusive upper date bound on run records, or ``None``.
        provider: Optional LLM run-record provider label filter (e.g.
            ``"llm:claude:sonnet"``, ``"claude"``); scopes ONLY the LLM
            run-timing section. This is distinct from an AEAT auth provider
            name -- the auth-session probe always auto-resolves its provider
            from workflow state (see ``auth_probe`` below) and never receives
            this filter.
        run_telemetry_recorder: Injected recorder (dependency injection for
            tests); defaults to the active-bucket
            :class:`~aeat.adapters.outbound.llm.LLMRunTelemetryRecorder`.
        auth_probe: Injected :class:`~aeat.application.auth.AuthTestResult`
            (dependency injection for tests); defaults to a fresh call to
            :func:`aeat.application.auth.test_operator_auth` with no provider
            override, so it reports whatever AEAT auth provider is configured
            in workflow state (or "none configured").

    Returns:
        The populated :class:`RunHealthReport`.
    """
    recorder = run_telemetry_recorder or LLMRunTelemetryRecorder()
    records = recorder.load_records(since=since, until=until)
    if provider is not None:
        records = tuple(item for item in records if item.provider == provider)
    llm_providers = _aggregate_runs(records)

    probe = auth_probe if auth_probe is not None else test_operator_auth()

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

    Mirrors :class:`~aeat.adapters.outbound.llm.LLMRunRecord` field-for-field;
    carries only accounting/timing metadata, never prompt or response text.
    """

    model_config = _STRICT_FROZEN

    run_id: str = Field(min_length=1)
    caller: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = ""
    duration_ms: int = Field(ge=0)
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

    Reuses :meth:`~aeat.adapters.outbound.llm.LLMRunTelemetryRecorder.load_records`
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
            :class:`~aeat.adapters.outbound.llm.LLMRunTelemetryRecorder`.

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


def _aggregate_runs(records: tuple[LLMRunRecord, ...]) -> tuple[LlmRunProviderMetrics, ...]:
    """Fold run records into one metrics row per provider, provider-sorted."""
    by_provider: dict[str, list[LLMRunRecord]] = {}
    for record in records:
        by_provider.setdefault(record.provider, []).append(record)
    rows: list[LlmRunProviderMetrics] = []
    for provider_name in sorted(by_provider):
        items = by_provider[provider_name]
        durations = [Decimal(item.duration_ms) for item in items]
        rows.append(
            LlmRunProviderMetrics(
                provider=provider_name,
                runs=len(items),
                succeeded=sum(1 for item in items if item.succeeded),
                failed=sum(1 for item in items if not item.succeeded),
                min_duration_ms=min(item.duration_ms for item in items),
                max_duration_ms=max(item.duration_ms for item in items),
                mean_duration_ms=(sum(durations, start=Decimal("0")) / Decimal(len(durations))).quantize(
                    Decimal("0.01"),
                ),
            ),
        )
    return tuple(rows)
