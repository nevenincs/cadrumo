"""Typed ``--json`` payload schemas for overview CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract test suite can
enumerate every overview-command surface this module covers.

Field sets match the production payload dicts constructed in ``_overview.py``
at their emit sites. All sequence fields use ``list`` rather than ``tuple``
because ``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays,
and the strict ``OutputSchema`` base does not coerce lists to tuples on
re-validation.

The nested calendar payloads mirror the JSON form of
:class:`~aeat.application.overview.OverviewCalendar`,
:class:`~aeat.application.overview.OverviewCalendarEntry`,
:class:`~aeat.application.overview.OverviewCalendarEvent`, and
:class:`~aeat.application.overview.OverviewCalendarFilingEvidence`.  Registered
result schemas then wrap those fragments for the
:class:`~aeat.entrypoints.cli._schemas.SchemaEnvelope` surface.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema

# ---------------------------------------------------------------------------
# Shared sub-models (not registered — used as nested types)
# ---------------------------------------------------------------------------


class OverviewDraftPayload(OutputSchema):
    """One draft row nested in a period-scoped :class:`OverviewStatusResult`."""

    draft_id: str
    modelo: str
    status: str


class OverviewCalendarEntryPayload(OutputSchema):
    """One :class:`~aeat.application.overview.OverviewCalendarEntry` row.

    The nested :class:`OverviewCalendarFilingEvidencePayload` keeps filing
    evidence beside the legal deadline row rather than flattening it into the
    command result.
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
    """Filing evidence nested in an :class:`OverviewCalendarEntryPayload`.

    Mirrors
    :class:`~aeat.application.overview.OverviewCalendarFilingEvidence` and keeps
    local filing state, observed AEAT submission state, and justificante
    verification as separate JSON fields.
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
    """One :class:`~aeat.application.overview.OverviewCalendarEvent` row."""

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
    """One :class:`~aeat.application.overview.CalendarWarning` row."""

    code: str
    message: str
    fix_command: str
    affected_modelos: list[str] = []


class OverviewCalendarRangePayload(OutputSchema):
    """JSON form of :class:`~aeat.application.overview.OverviewCalendarRange`."""

    from_date: str
    to_date: str


class OverviewCalendarCompletenessPayload(OutputSchema):
    """JSON form of :class:`~aeat.application.overview.CalendarCompleteness`."""

    explicitly_set_keys: list[str] = []
    defaulted_keys: list[str] = []
    computable_modelos: list[str] = []
    defaulted_modelos: list[str] = []


class OverviewSuppressedCalendarEntryPayload(OutputSchema):
    """JSON form of :class:`~aeat.application.overview.SuppressedCalendarEntry`."""

    modelo: str
    period: str
    verdict: str
    reason: str


class OverviewCalendarPayload(OutputSchema):
    """Typed :class:`~aeat.application.overview.OverviewCalendar` JSON fragment."""

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
    """One profile block in ``overview calendar --all-profiles`` mode."""

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
    uses :class:`OverviewDraftPayload` rows for the scoped draft list.
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
    consumer which branch produced the payload.
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
    application read model remains the payload authority.
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
    controls only envelope registration and rendering.
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
    applicability verdict, legal references, and profile facts.
    """

    modelo: str | None = None
    year: int | None = None
    applicable: bool | None = None
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]
