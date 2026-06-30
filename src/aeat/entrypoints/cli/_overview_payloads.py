"""Typed ``--json`` payload schemas for overview CLI commands.

Each class declared here is a strict
:class:`~aeat.entrypoints.cli._schemas.OutputSchema` subclass and is decorated
with :func:`~aeat.entrypoints.cli._schemas.register_schema` so the
JSON-contract test suite can enumerate every overview-command surface this
module covers.

Field sets match the production payload dicts constructed in
:mod:`~aeat.entrypoints.cli._overview` at their emit sites. All sequence fields
use ``list`` rather than ``tuple`` because ``model_dump(mode='json')``
serialises pydantic tuples as JSON arrays, and the strict
:class:`~aeat.entrypoints.cli._schemas.OutputSchema` base does not coerce lists
to tuples on re-validation.

The nested calendar payloads mirror the JSON form of
:class:`~aeat.application.overview.OverviewCalendar`,
:class:`~aeat.application.overview.OverviewCalendarEntry`,
:class:`~aeat.application.overview.OverviewCalendarEvent`, and
:class:`~aeat.application.overview.OverviewCalendarFilingEvidence`. Registered
result schemas then wrap those fragments, plus read models returned by
:func:`~aeat.application.overview.build_overview_status_report`,
:func:`~aeat.application.overview.build_overview_agenda`,
:func:`~aeat.application.overview.build_overview_backlog`, and
:func:`~aeat.application.overview.build_overview_explain`, for the
:class:`~aeat.entrypoints.cli._schemas.SchemaEnvelope` surface through
:func:`~aeat.entrypoints.cli._common._emit_envelope`. The application overview
package remains the source of business semantics; this module only documents
and validates the transport shape emitted by
:mod:`~aeat.entrypoints.cli._overview`.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema

# ---------------------------------------------------------------------------
# Shared sub-models (not registered — used as nested types)
# ---------------------------------------------------------------------------


class OverviewDraftPayload(OutputSchema):
    """One draft row nested in a period-scoped overview status result.

    Nested in
    :class:`~aeat.entrypoints.cli._overview_payloads.OverviewStatusResult`. The
    full-status branch forwards
    :class:`~aeat.application.overview.OverviewStatusReport` counters, while the
    period branch expands the selected :class:`~aeat.domain.filing.ModeloDraft`
    records into these small JSON rows.
    """

    draft_id: str
    modelo: str
    status: str


class OverviewCalendarEntryPayload(OutputSchema):
    """One :class:`~aeat.application.overview.OverviewCalendarEntry` row.

    The nested
    :class:`~aeat.entrypoints.cli._overview_payloads.OverviewCalendarFilingEvidencePayload`
    keeps filing
    evidence beside the legal deadline row rather than flattening it into the
    command result. Deadline fields remain the legal schedule from
    :class:`~aeat.domain.deadlines.ModeloDeadline`; local and observed filing
    state are carried separately on the evidence payload.
    """

    modelo: str
    period: str
    opens_on: str
    closes_on: str
    adjusted_closes_on: str
    shift_reason: str | None = None
    holiday_refs: list[str] = []
    jurisdictions: list[str] = []
    payment_cutoff_on: str | None = None
    status: str
    user_state: str
    recovery: dict[str, object] | None = None
    filing_year: int | None = None
    censo_enrolment_state: str
    filing_evidence: OverviewCalendarFilingEvidencePayload


class OverviewCalendarFilingEvidencePayload(OutputSchema):
    """Filing evidence nested in an overview calendar entry payload.

    Nested in
    :class:`~aeat.entrypoints.cli._overview_payloads.OverviewCalendarEntryPayload`.
    Mirrors
    :class:`~aeat.application.overview.OverviewCalendarFilingEvidence` and keeps
    local filing state, observed AEAT submission state, and justificante
    verification as separate JSON fields. That distinction preserves the
    application rule that a local filed record is not an AEAT submission and an
    observed submission is not a verified justificante until CSV evidence
    proves the match.
    """

    modelo: str | None = None
    filing_year: int | None = None
    period: str | None = None
    local_filing_state: str
    local_filing_record_id: str | None = None
    local_calculation_revision_id: str | None = None
    local_filed_at: str | None = None
    aeat_submission_state: str
    aeat_submitted_at: str | None = None
    aeat_reference_id: str | None = None
    aeat_snapshot_id: str | None = None
    aeat_evidence_kind: str | None = None
    aeat_evidence_conflict_reference_ids: list[str] = []
    verified_justificante_csv: str | None = None
    justificante_required: bool
    justificante_verified: bool
    evidence_source: str | None = None


class OverviewCalendarEventPayload(OutputSchema):
    """One :class:`~aeat.application.overview.OverviewCalendarEvent` row.

    Events are additive observations beside the legal calendar, such as filed
    declarations or notifications loaded from persisted live snapshots. Optional
    filing fields mirror the application event model without upgrading the
    corresponding
    :class:`~aeat.entrypoints.cli._overview_payloads.OverviewCalendarEntryPayload`
    evidence row by
    themselves.
    """

    event_type: str
    event_date: str
    source: str
    summary: str
    reference_id: str
    snapshot_id: str | None = None
    modelo: str | None = None
    filing_year: int | None = None
    period: str | None = None
    status: str | None = None
    source_url: str | None = None
    aeat_submission_state: str | None = None
    aeat_submitted_at: str | None = None
    justificante_verified: bool | None = None
    verified_justificante_csv: str | None = None


class OverviewCalendarWarningPayload(OutputSchema):
    """One :class:`~aeat.application.overview.CalendarWarning` row.

    Warnings identify profile keys whose missing values forced the calendar
    builder to use deadline-engine defaults. ``affected_modelos`` mirrors the
    application row so consumers can show which obligations may depend on the
    suggested ``fix_command``.
    """

    code: str
    message: str
    fix_command: str
    affected_modelos: list[str] = []


class OverviewCalendarRangePayload(OutputSchema):
    """JSON form of :class:`~aeat.application.overview.OverviewCalendarRange`.

    The application range is inclusive; the CLI schema keeps the same
    ``from_date`` / ``to_date`` keys as ISO strings inside calendar and backlog
    payloads.
    """

    from_date: str
    to_date: str


class OverviewCalendarCompletenessPayload(OutputSchema):
    """JSON form of :class:`~aeat.application.overview.CalendarCompleteness`.

    The tuple fields from the application DTO become JSON arrays so the
    envelope can report which profile keys were explicit, which defaulted, and
    which modelos were still computable.
    """

    explicitly_set_keys: list[str] = []
    defaulted_keys: list[str] = []
    computable_modelos: list[str] = []
    defaulted_modelos: list[str] = []


class OverviewSuppressedCalendarEntryPayload(OutputSchema):
    """JSON form of :class:`~aeat.application.overview.SuppressedCalendarEntry`.

    These rows exist only when the calendar command asks to retain
    non-applicable obligations; they preserve the applicability verdict and
    reason without reintroducing the row into ``entries``.
    """

    modelo: str
    period: str
    verdict: str
    reason: str


class OverviewCalendarPayload(OutputSchema):
    """Typed :class:`~aeat.application.overview.OverviewCalendar` JSON fragment.

    Used by ``overview calendar --all-profiles`` profile blocks and by typed
    conformance checks. The payload keeps legal entries, additive events,
    completeness, warnings, and suppressed rows in the same compartments as the
    application read model.
    """

    range: OverviewCalendarRangePayload
    entries: list[OverviewCalendarEntryPayload] = []
    generated_at: str
    warnings: list[OverviewCalendarWarningPayload] = []
    completeness: OverviewCalendarCompletenessPayload
    taxpayer_model_declared: bool
    incomplete_reason: str | None = None
    suppressed_entries: list[OverviewSuppressedCalendarEntryPayload] = []
    events: list[OverviewCalendarEventPayload] = []


class OverviewCalendarProfilePayload(OutputSchema):
    """One profile block in ``overview calendar --all-profiles`` mode.

    The embedded
    :class:`~aeat.entrypoints.cli._overview_payloads.OverviewCalendarPayload`
    is the full calendar result for that profile.
    :class:`~aeat.entrypoints.cli._overview_payloads.OverviewCalendarResult`
    then carries these blocks
    under ``profiles``, keeping all-profile output typed instead of falling back
    to a raw nested ``dict``.
    """

    profile_id: str
    label: str
    calendar: OverviewCalendarPayload


# ---------------------------------------------------------------------------
# Registered schemas
# ---------------------------------------------------------------------------


@register_schema("overview.status")
class OverviewStatusResult(OutputSchema):
    """JSON envelope result for ``aeat app overview status``.

    The full-status branch accepts the JSON form of
    :class:`~aeat.application.overview.OverviewStatusReport`; the period branch
    uses :class:`~aeat.entrypoints.cli._overview_payloads.OverviewDraftPayload`
    rows derived from matching
    :class:`~aeat.domain.filing.ModeloDraft` records for the scoped draft list.
    The application report is derived from
    :class:`~aeat.application.state_projection.OperatorStateProjection`; this
    schema only bounds the CLI envelope branch and permits future report fields
    through ``extra='allow'``.
    """

    # Period-scoped branch fields
    period: str | None = None
    # The period-scoped branch emits a list of draft payloads; the
    # full-status passthrough branch emits an ``int`` count derived from
    # ``OverviewStatusReport.drafts``. Both shapes share the JSON key.
    drafts: int | list[OverviewDraftPayload] | None = None
    verbose: bool | None = None

    # Full status-report passthrough (model_dump of OverviewStatusReport).
    # The status report is an application-layer pydantic model; the full
    # shape is forwarded as-is. We accept extra fields so any new keys
    # the application model adds don't break the conformance gate.
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("overview.calendar")
class OverviewCalendarResult(OutputSchema):
    """JSON envelope for ``aeat app overview calendar``.

    Covers both the single-profile mode (``entries``/``warnings``/
    ``suppressed_entries`` populated) and the ``--all-profiles`` mode
    (``profiles`` populated, single-profile fields empty). The same
    envelope key serves the leaf so the JSON-contract registry holds
    exactly one schema per CLI leaf; the populated field set tells the
    consumer which branch produced the payload. Both branches still mirror the
    same :class:`~aeat.application.overview.OverviewCalendar` compartments.
    """

    from_date: str | None = None
    to_date: str | None = None
    entries: list[OverviewCalendarEntryPayload] = []
    events: list[OverviewCalendarEventPayload] = []
    warnings: list[OverviewCalendarWarningPayload] = []
    suppressed_entries: list[OverviewSuppressedCalendarEntryPayload] = []
    profiles: list[OverviewCalendarProfilePayload] = []
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("overview.agenda")
class OverviewAgendaResult(OutputSchema):
    """JSON envelope result for ``aeat app overview agenda``.

    Accepts the JSON form of
    :class:`~aeat.application.overview._agenda.OverviewAgenda` so the
    application read model remains the payload authority. That model reuses
    :class:`~aeat.application.overview.OverviewCalendarEntry`,
    :class:`~aeat.application.overview.CalendarWarning`, and
    :class:`~aeat.application.overview.CalendarCompleteness` rows from the
    calendar build.
    """

    as_of: str | None = None
    horizon_days: int | None = None
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("overview.backlog")
class OverviewBacklogResult(OutputSchema):
    """JSON envelope result for ``aeat app overview backlog``.

    Accepts the JSON form of
    :class:`~aeat.application.overview._backlog.OverviewBacklog` while the CLI
    controls only envelope registration and rendering. The backlog read model
    is a filtered :class:`~aeat.application.overview.OverviewCalendar`
    projection, so its items remain calendar entry rows rather than
    command-local DTOs.
    """

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("overview.explain")
class OverviewExplainResult(OutputSchema):
    """JSON envelope result for ``aeat app overview explain``.

    Accepts the JSON form of
    :class:`~aeat.application.overview._explain.OverviewExplain`, including the
    applicability verdict, legal references, and profile facts. The verdict is
    the registry-grounded
    :class:`~aeat.domain.calculations.registry.applicability.ApplicabilityVerdict`,
    not a deadline-window guess made by the CLI.
    """

    modelo: str | None = None
    year: int | None = None
    applicable: bool | None = None
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]
