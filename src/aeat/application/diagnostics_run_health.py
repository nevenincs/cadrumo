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
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ..adapters.outbound.llm import LLMRunRecord, LLMRunTelemetryRecorder
from .auth import AuthTestResult, test_operator_auth

__all__ = [
    "LlmRunProviderMetrics",
    "RunHealthReport",
    "build_run_health_report",
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
