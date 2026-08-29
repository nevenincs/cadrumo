"""Typed ``--json`` payload schemas for ``aeat app diagnostics`` commands.

Every declared payload is an :class:`OutputSchema` subclass referenced by
production-authored CommandSpec as deferred public schema targets for the local-only run-health diagnostic surface
carried by :class:`SchemaEnvelope` through :func:`emit_envelope`. These
schemas project :class:`~application.diagnostics_run_health.RunHealthReport`,
:class:`~application.diagnostics_run_health.LatencyReport`,
:class:`~application.diagnostics_run_health.ErrorsBreakdownReport`, and
:class:`~application.diagnostics_run_health.LlmUsageReport` into the CLI
JSON contract.

See Also:
    :mod:`~entrypoints.cli._app_diagnostics`
        CLI transport that populates the local-only diagnostics payloads.
    :mod:`~entrypoints.cli._app_diagnostics_telemetry`
        CLI transport that populates the telemetry status/flush payloads.
    :mod:`~application.diagnostics_run_health`
        Application report models mirrored by the run-health payload family.
    :mod:`~application.diagnostics_telemetry`
        Application posture/flush models mirrored by the telemetry payload
        family.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, NonNegativeInt, field_validator, model_validator

from ...core.decimal import try_parse_canonical_decimal
from ...core.json_contract import OutputSchema
from ...core.telemetry import TelemetryEventPayload, TelemetryTier
from ...core.time import validate_inclusive_iso_date_range
from ...core.unit_proportion import is_unit_proportion
from ._decimal_wire import DecimalWireText


# The canonical run-health models express these bounds on real int/Decimal
# fields; the transport carries rendered strings for the decimals, so the same
# bound is re-asserted on the text. Duration and percentile fields are
# deliberately left unbounded because the canonical models leave them so --
# the transport mirrors the canonical contract rather than inventing a
# stricter one.
def _validate_success_rate(value: str) -> str:
    """Keep successful-run ratios within the canonical closed 0..1 interval."""
    parsed = try_parse_canonical_decimal(value, signed=True)
    if parsed is None:
        raise ValueError(f"{value!r} is not a canonical decimal string")
    if not is_unit_proportion(parsed):
        raise ValueError(f"{value!r} must be between 0 and 1")
    return value


class LlmRunProviderPayload(OutputSchema):
    """One provider's aggregated local LLM run-timing metrics.

    Mirrors :class:`~application.diagnostics_run_health.LlmRunProviderMetrics`.
    """

    provider: str = Field(min_length=1)
    runs: NonNegativeInt
    succeeded: NonNegativeInt
    failed: NonNegativeInt
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    mean_duration_ms: DecimalWireText | None = None


class RunHealthResult(OutputSchema):
    """JSON envelope for ``aeat app diagnostics run-health``.

    Presents local-only LLM run-timing telemetry (per-provider run counts,
    outcomes, and duration distribution) alongside the persisted-AEAT-session
    staleness probe in one read-only report, both sourced from
    :func:`~application.diagnostics_run_health.build_run_health_report`. It
    reports only accounting/timing metadata, never prompt or response content.
    """

    since: str | None = None
    until: str | None = None
    llm_providers: list[LlmRunProviderPayload]
    total_runs: NonNegativeInt
    total_succeeded: NonNegativeInt
    total_failed: NonNegativeInt

    @model_validator(mode="after")
    def _window_is_not_empty(self) -> RunHealthResult:
        """Carry the canonical window invariant onto the wire boundary.

        The bounds are serialised ``date.isoformat()`` output, so the
        same closed-interval contract the report enforces applies here;
        without it a directly-constructed or deserialized envelope can
        still publish a window the report itself would refuse.
        """
        validate_inclusive_iso_date_range(self.since, self.until)
        return self

    has_run_data: bool
    auth_provider: str
    auth_configured: bool
    persisted_session_present: bool
    persisted_session_expired: bool | None = None
    persisted_session_state: str
    probe_summary: str
    session_stale: bool


class RunRecordPayload(OutputSchema):
    """One individual local LLM run-timing record.

    Mirrors :class:`~application.diagnostics_run_health.RunRecordView`.
    """

    run_id: str = Field(min_length=1)
    caller: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    # `model` and `error_kind` stay unbounded: the canonical RunRecordView
    # defaults both to the empty string, so a blank is representable.
    model: str
    duration_ms: NonNegativeInt
    succeeded: bool
    error_kind: str
    started_at: datetime


class RunsListResult(OutputSchema):
    """JSON envelope for ``aeat app diagnostics runs``.

    Lists individual local LLM run-timing records, most-recent-first, sourced
    from :func:`~application.diagnostics_run_health.list_recent_runs`. It
    reports only accounting/timing metadata, never prompt or response content.
    """

    since: str | None = None
    until: str | None = None
    provider: str | None = None
    # ge=1 mirrors the ``--limit`` option's own ``min=1``: a zero cap is a
    # listing that can never return a row, which the command itself refuses.
    limit: int | None = Field(default=None, ge=1)
    runs: list[RunRecordPayload]
    total_runs: int
    has_run_data: bool

    @model_validator(mode="after")
    def _window_is_not_empty(self) -> RunsListResult:
        """Carry the canonical window invariant onto the wire boundary.

        The bounds are serialised ``date.isoformat()`` output, so the
        same closed-interval contract the report enforces applies here;
        without it a directly-constructed or deserialized envelope can
        still publish a window the report itself would refuse.
        """
        validate_inclusive_iso_date_range(self.since, self.until)
        return self


class LatencyPercentilesPayload(OutputSchema):
    """Percentile and summary latency statistics for one scope (overall or one provider).

    Mirrors :class:`~application.diagnostics_run_health.LatencyPercentiles`.
    """

    entries: int = Field(default=0, ge=0)
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    mean_duration_ms: DecimalWireText | None = None
    p50_duration_ms: int | None = None
    p95_duration_ms: int | None = None
    p99_duration_ms: int | None = None


class LatencyProviderRowPayload(OutputSchema):
    """One provider's :class:`LatencyPercentilesPayload` row."""

    provider: str = Field(min_length=1)
    percentiles: LatencyPercentilesPayload


class LatencyResult(OutputSchema):
    """JSON envelope for ``aeat app diagnostics latency``.

    Presents P50/P95/P99 (plus min/max/mean) run-duration percentiles overall
    and, unless ``--provider`` scopes the query, broken down per provider.
    Sourced from
    :func:`~application.diagnostics_run_health.build_latency_report`. It
    reports only accounting/timing metadata, never prompt or response content.
    """

    since: str | None = None
    until: str | None = None
    provider: str | None = None
    overall: LatencyPercentilesPayload
    by_provider: list[LatencyProviderRowPayload]
    has_run_data: bool

    @model_validator(mode="after")
    def _window_is_not_empty(self) -> LatencyResult:
        """Carry the canonical window invariant onto the wire boundary.

        The bounds are serialised ``date.isoformat()`` output, so the
        same closed-interval contract the report enforces applies here;
        without it a directly-constructed or deserialized envelope can
        still publish a window the report itself would refuse.
        """
        validate_inclusive_iso_date_range(self.since, self.until)
        return self


class ErrorKindCountPayload(OutputSchema):
    """One provider/``error_kind`` failure count.

    Mirrors :class:`~application.diagnostics_run_health.ErrorKindCount`.
    """

    error_kind: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    # ge=1, not ge=0: the canonical ErrorKindCount only materialises a row for
    # an error kind that actually occurred, so a zero-count row is not a
    # representable observation.
    count: int = Field(ge=1)


class ErrorsBreakdownResult(OutputSchema):
    """JSON envelope for ``aeat app diagnostics errors``.

    Presents a breakdown of failed LLM runs by provider and ``error_kind``,
    sorted by descending failure count. Sourced from
    :func:`~application.diagnostics_run_health.build_error_breakdown`. It
    reports only accounting/timing metadata, never prompt or response content.
    """

    since: str | None = None
    until: str | None = None
    provider: str | None = None
    total_runs: NonNegativeInt
    total_failed: NonNegativeInt
    by_error_kind: list[ErrorKindCountPayload]
    has_failures: bool

    @model_validator(mode="after")
    def _window_is_not_empty(self) -> ErrorsBreakdownResult:
        """Carry the canonical window invariant onto the wire boundary.

        The bounds are serialised ``date.isoformat()`` output, so the
        same closed-interval contract the report enforces applies here;
        without it a directly-constructed or deserialized envelope can
        still publish a window the report itself would refuse.
        """
        validate_inclusive_iso_date_range(self.since, self.until)
        return self


class LlmUsageModelPayload(OutputSchema):
    """One provider's per-model aggregated run-usage metrics.

    Mirrors :class:`~application.diagnostics_run_health.LlmUsageModelMetrics`.
    """

    # `model` stays unbounded: the canonical LlmUsageModelMetrics defaults it
    # to the empty string.
    model: str
    runs: NonNegativeInt
    succeeded: NonNegativeInt
    failed: NonNegativeInt
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    mean_duration_ms: DecimalWireText | None = None
    total_duration_ms: int = Field(default=0, ge=0)
    success_rate: DecimalWireText

    @field_validator("success_rate")
    @classmethod
    def _success_rate_is_bounded(cls, value: str) -> str:
        return _validate_success_rate(value)


class LlmRunHealthProviderPayload(OutputSchema):
    """One provider's aggregated run-usage metrics, plus its per-model breakdown.

    Mirrors :class:`~application.diagnostics_run_health.LlmRunHealthProviderMetrics`.
    """

    provider: str = Field(min_length=1)
    runs: NonNegativeInt
    succeeded: NonNegativeInt
    failed: NonNegativeInt
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    mean_duration_ms: DecimalWireText | None = None
    total_duration_ms: int = Field(default=0, ge=0)
    success_rate: DecimalWireText
    models: list[LlmUsageModelPayload]

    @field_validator("success_rate")
    @classmethod
    def _success_rate_is_bounded(cls, value: str) -> str:
        return _validate_success_rate(value)


class LlmUsageResult(OutputSchema):
    """JSON envelope for ``aeat app diagnostics llm-usage``.

    Presents a run-count/duration/success-rate usage summary grouped by
    provider and, within each provider, by model. Sourced from
    :func:`~application.diagnostics_run_health.build_llm_usage_report`,
    which projects the same recorded
    :class:`~adapters.outbound.llm.LLMRunRecord` telemetry every sibling
    diagnostics verb reads -- no new capture or storage path. That record
    carries no token counts, so this is a run/timing/success-rate summary
    rather than a token-usage summary; it reports only accounting/timing
    metadata, never prompt or response content.
    """

    since: str | None = None
    until: str | None = None
    provider: str | None = None
    by_provider: list[LlmRunHealthProviderPayload]

    @model_validator(mode="after")
    def _window_is_not_empty(self) -> LlmUsageResult:
        """Carry the canonical window invariant onto the wire boundary.

        The bounds are serialised ``date.isoformat()`` output, so the
        same closed-interval contract the report enforces applies here;
        without it a directly-constructed or deserialized envelope can
        still publish a window the report itself would refuse.
        """
        validate_inclusive_iso_date_range(self.since, self.until)
        return self

    total_runs: int
    total_succeeded: int
    total_failed: int
    overall_success_rate: str
    has_run_data: bool


class TelemetryStatusResult(OutputSchema):
    """JSON envelope for ``aeat app diagnostics telemetry status``.

    Mirrors :class:`~application.diagnostics_telemetry.TelemetryStatusReport`.
    Default-off, consent-gated remote telemetry posture; this verb never
    emits anything, it only reports the currently-effective :class:`~core.config.Settings`
    fields plus the derived verdict a fully-acknowledged invocation would
    currently receive.
    """

    opt_in: bool
    tier: TelemetryTier
    gestor_mode: bool
    endpoint: str | None = None
    would_emit_if_acknowledged: bool


class TelemetryFlushResult(OutputSchema):
    """JSON envelope for ``aeat app diagnostics telemetry flush``.

    Mirrors :class:`~application.diagnostics_telemetry.TelemetryFlushPreview`.
    ``dry_run=True`` never performs a network call regardless of ``sent``;
    ``sent`` reports whether a real (non-dry-run) invocation actually handed
    the payload to the HTTP sink (``gate_permits and endpoint_configured``).
    """

    dry_run: bool
    payload: TelemetryEventPayload
    gate_permits: bool
    endpoint_configured: bool
    would_send: bool
    sent: bool
