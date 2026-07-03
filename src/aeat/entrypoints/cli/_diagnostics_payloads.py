"""Typed ``--json`` payload schemas for ``aeat app diagnostics`` commands.

Every declared payload is an :class:`OutputSchema` subclass registered with
:func:`register_schema` for the local-only run-health diagnostic surface
carried by :class:`SchemaEnvelope` through :func:`_emit_envelope`. These
schemas project :class:`~aeat.application.diagnostics_run_health.RunHealthReport`
into the CLI JSON contract.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema


class LlmRunProviderPayload(OutputSchema):
    """One provider's aggregated local LLM run-timing metrics.

    Mirrors :class:`~aeat.application.diagnostics_run_health.LlmRunProviderMetrics`.
    """

    provider: str
    runs: int
    succeeded: int
    failed: int
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    mean_duration_ms: str | None = None


@register_schema("diagnostics.run_health")
class RunHealthResult(OutputSchema):
    """JSON envelope for ``aeat app diagnostics run-health``.

    Presents local-only LLM run-timing telemetry (per-provider run counts,
    outcomes, and duration distribution) alongside the persisted-AEAT-session
    staleness probe in one read-only report, both sourced from
    :func:`~aeat.application.diagnostics_run_health.build_run_health_report`. It
    reports only accounting/timing metadata, never prompt or response content.
    """

    since: str | None = None
    until: str | None = None
    llm_providers: list[LlmRunProviderPayload]
    total_runs: int
    total_succeeded: int
    total_failed: int
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

    Mirrors :class:`~aeat.application.diagnostics_run_health.RunRecordView`.
    """

    run_id: str
    caller: str
    provider: str
    model: str
    duration_ms: int
    succeeded: bool
    error_kind: str
    started_at: str


@register_schema("diagnostics.runs")
class RunsListResult(OutputSchema):
    """JSON envelope for ``aeat app diagnostics runs``.

    Lists individual local LLM run-timing records, most-recent-first, sourced
    from :func:`~aeat.application.diagnostics_run_health.list_recent_runs`. It
    reports only accounting/timing metadata, never prompt or response content.
    """

    since: str | None = None
    until: str | None = None
    provider: str | None = None
    limit: int | None = None
    runs: list[RunRecordPayload]
    total_runs: int
    has_run_data: bool
