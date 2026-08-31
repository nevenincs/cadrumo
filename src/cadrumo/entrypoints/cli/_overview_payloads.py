"""Typed ``--json`` payload schemas for overview CLI commands.

Each class declared here is a strict
:class:`OutputSchema` subclass and a deferred public schema target referenced
by production-authored CommandSpec so
the JSON-contract test suite can enumerate every overview-command surface this
module covers.

Field sets match the production payload dicts constructed in
:mod:`_overview` at their emit sites. All sequence fields use ``list`` rather
than ``tuple`` because ``model_dump(mode='json')`` serialises pydantic tuples as
JSON arrays, and the strict :class:`OutputSchema` base does not coerce lists to
tuples on re-validation.

The nested calendar payloads mirror the JSON form of
:class:`OverviewCalendar`, :class:`OverviewCalendarEntry`,
:class:`OverviewCalendarEvent`, and
:class:`OverviewCalendarFilingEvidence`. Graph-declared result schemas then wrap
those fragments, plus read models returned by
:func:`build_overview_status_report`, :func:`build_overview_agenda`,
:func:`build_overview_backlog`, and :func:`build_overview_explain`, for the
:class:`SchemaEnvelope` surface through :func:`emit_envelope`. The application
overview package remains the source of business semantics; this module only
documents and validates the transport shape emitted by :mod:`_overview`.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import NonNegativeInt, model_validator

from ...application.operator_actions._models import ActionReference
from ...application.overview.data_prep import DataPrepStepId, DataPrepStepState
from ...application.overview.pipeline_health import ModeloReadinessState
from ...core.identity import AeatCsv, CalculationRevisionId, FilingRecordId, ProfileId, SnapshotId, WorkUnitId
from ...core.json_contract import OutputSchema, ResolvedActionArgument, ResolvedNoticeAction
from ...core.parsing import require_iso8601_date
from ._ledger_payloads import LedgerStatusResult

# ---------------------------------------------------------------------------
# Shared nested models (not direct CommandSpec schema targets)
# ---------------------------------------------------------------------------


class OverviewDraftPayload(OutputSchema):
    """One draft row nested in a period-scoped overview status result.

    Nested in
    :class:`OverviewStatusResult`. The full-status branch forwards
    :class:`OverviewStatusReport` counters, while the period branch expands the
    selected :class:`ModeloDraft` records into these small JSON rows.
    """

    draft_id: str
    modelo: str
    status: str


class OverviewCalendarFilingEvidencePayload(OutputSchema):
    """Filing evidence nested in an overview calendar entry payload.

    Mirrors :class:`OverviewCalendarFilingEvidence` and keeps local filing state,
    observed AEAT submission state, and justificante verification as separate
    JSON fields. That distinction preserves the application rule that a local
    filed record is not an AEAT submission and an observed submission is not a
    verified justificante until CSV evidence proves the match.
    """

    modelo: str | None = None
    filing_year: int | None = None
    period: str | None = None
    local_filing_state: Literal["not_ready_to_file", "ready_to_file", "external_baseline_imported"]
    local_filing_record_id: FilingRecordId | None = None
    local_calculation_revision_id: CalculationRevisionId | None = None
    local_filed_at: str | None = None
    aeat_submission_state: Literal["not_observed", "submitted_observed", "accepted", "justificante_verified"]
    aeat_submitted_at: str | None = None
    aeat_reference_id: str | None = None
    aeat_snapshot_id: SnapshotId | None = None
    aeat_evidence_kind: str | None = None
    aeat_evidence_conflict_reference_ids: list[str] = []
    verified_justificante_csv: AeatCsv | None = None
    justificante_required: bool
    justificante_verified: bool
    evidence_source: str | None = None

    @model_validator(mode="after")
    def _require_csv_for_verified_justificante(self) -> OverviewCalendarFilingEvidencePayload:
        verified_state = self.aeat_submission_state == "justificante_verified"
        if self.justificante_verified != verified_state:
            raise ValueError("justificante_verified must agree with aeat_submission_state")
        if verified_state != (self.verified_justificante_csv is not None):
            raise ValueError("verified_justificante_csv must be present exactly for verified justificantes")
        return self


class OverviewCalendarEventPayload(OutputSchema):
    """One :class:`OverviewCalendarEvent` row.

    Events are additive observations beside the legal calendar, such as filed
    declarations or notifications loaded from persisted live snapshots. Optional
    filing fields mirror the application event model without upgrading a
    calendar entry's own evidence row by themselves.
    """

    event_type: Literal["filing", "message"]
    post_filing_kind: str | None = None
    #: The Ley 39/2015 art. 43.2 service state of a notification — still inside
    #: its access window, accessed, or lapsed into deemed-served. Operator-facing
    #: procedural status, not an identifier, so it is mirrored here rather than
    #: withheld. The event model's ``authenticated_identity`` is deliberately
    #: absent instead: it carries a taxpayer NIF and is ``exclude=True`` at the
    #: source, so it never reaches this projection and must not be added.
    notificacion_estado_servicio: str | None = None
    event_date: str
    source: str
    summary: str
    reference_id: str
    snapshot_id: SnapshotId | None = None
    modelo: str | None = None
    filing_year: int | None = None
    period: str | None = None
    status: str | None = None
    source_url: str | None = None
    aeat_submission_state: Literal["not_observed", "submitted_observed", "accepted", "justificante_verified"] | None = (
        None
    )
    aeat_submitted_at: str | None = None
    justificante_verified: bool | None = None
    verified_justificante_csv: AeatCsv | None = None

    @model_validator(mode="after")
    def _require_event_csv_for_verified_justificante(self) -> OverviewCalendarEventPayload:
        verified_state = self.aeat_submission_state == "justificante_verified"
        if self.justificante_verified is True and not verified_state:
            raise ValueError("justificante_verified requires a verified AEAT submission state")
        if verified_state and (self.justificante_verified is not True or self.verified_justificante_csv is None):
            raise ValueError("verified AEAT submission requires justificante CSV evidence")
        if not verified_state and self.verified_justificante_csv is not None:
            raise ValueError("justificante CSV evidence requires a verified AEAT submission state")
        return self


class OverviewCalendarEntrySummaryPayload(OutputSchema):
    """Actionable calendar row summary with a typed route to full explanation.

    The calendar list answers what is due and whether filing evidence has been
    observed. Legal-window and recovery detail stays retrievable through the
    resolved ``overview explain`` action instead of being repeated for every
    row in the tool-list schema.
    """

    modelo: str
    period: str
    adjusted_closes_on: str
    user_state: Literal["due", "late", "filed", "unknown"]
    censo_enrolment_state: Literal["not_checked", "not_required", "unverified", "verified"]
    local_filing_state: Literal["not_ready_to_file", "ready_to_file", "external_baseline_imported"]
    aeat_submission_state: Literal["not_observed", "submitted_observed", "accepted", "justificante_verified"]
    justificante_verified: bool
    detail_action: ResolvedNoticeAction


class OverviewCalendarEventSummaryPayload(OutputSchema):
    """Compact observed-event identity retained by the calendar list.

    ``source`` plus ``reference_id`` are the stable retrieval coordinates for
    the owning live-read surface; the full event record is not redeclared in
    every calendar result schema.
    """

    event_type: Literal["filing", "message"]
    event_date: str
    source: str
    summary: str
    reference_id: str
    status: str | None = None
    aeat_submission_state: Literal["not_observed", "submitted_observed", "accepted", "justificante_verified"] | None = (
        None
    )
    aeat_submitted_at: str | None = None
    justificante_verified: bool | None = None


class OverviewResolvedWarningActionReferencePayload(OutputSchema):
    """Resolved command target retaining the producer's stable action identity."""

    action: ActionReference
    target_command_key: str
    cli_path: list[str]
    arguments: dict[str, str] | None = None


class OverviewResolvedWarningActionPayload(OutputSchema):
    """Calendar-warning action in the established declared-action wire envelope."""

    action: OverviewResolvedWarningActionReferencePayload
    argument_bindings: list[ResolvedActionArgument] = []


class OverviewCalendarWarningPayload(OutputSchema):
    """One :class:`CalendarWarning` row.

    Warnings identify profile keys whose missing values forced the calendar
    builder to use deadline-engine defaults. ``affected_modelos`` mirrors the
    application row so consumers can show which obligations may depend on the
    remedy.

    ``fix_action`` is the same schema-resolved action carried by the envelope
    notice. The CLI resolves the application's declaration once through the
    command catalogue and reuses that value; it does not reconstruct guidance.
    """

    code: str
    message: str
    affected_modelos: list[str] = []
    fix_action: OverviewResolvedWarningActionPayload


class OverviewCalendarRangePayload(OutputSchema):
    """JSON form of :class:`OverviewCalendarRange`.

    The application range is inclusive; the CLI schema keeps the same
    ``from_date`` / ``to_date`` keys as ISO strings inside calendar and backlog
    payloads.
    """

    from_date: str
    to_date: str

    @model_validator(mode="after")
    def _enforce_inclusive_date_order(self) -> OverviewCalendarRangePayload:
        try:
            from_date = require_iso8601_date(self.from_date)
            to_date = require_iso8601_date(self.to_date)
        except ValueError as exc:
            raise ValueError("calendar range dates must be ISO-8601 dates") from exc
        if from_date > to_date:
            raise ValueError("calendar range from_date cannot be after to_date")
        return self


class OverviewCalendarCompletenessPayload(OutputSchema):
    """JSON form of :class:`CalendarCompleteness`.

    The tuple fields from the application DTO become JSON arrays so the
    envelope can report which profile keys were explicit, which defaulted, and
    which modelos were still computable.
    """

    explicitly_set_keys: list[str] = []
    defaulted_keys: list[str] = []
    computable_modelos: list[str] = []
    defaulted_modelos: list[str] = []


class OverviewSuppressedCalendarEntryPayload(OutputSchema):
    """JSON form of :class:`SuppressedCalendarEntry`.

    These rows exist only when the calendar command asks to retain
    non-applicable obligations; they preserve the applicability verdict and
    reason without reintroducing the row into ``entries``.
    """

    modelo: str
    period: str
    verdict: str
    reason: str


class OverviewAdvisedObligationPayload(OutputSchema):
    """One obligation the calendar could not positively scope."""

    modelo: str
    reason: Literal[
        "applicable_window_missing",
        "applicability_undetermined",
        "registry_unmodeled",
    ]


class OverviewObligationCoveragePayload(OutputSchema):
    """JSON projection of the canonical total obligation-coverage partition.

    Each modelo occurs in exactly one disposition. That invariant belongs to the
    canonical :class:`~application.overview.ObligationCoverageReport`, which
    refuses to construct a self-contradicting partition, so every consumer of
    the application layer inherits it rather than only the JSON surface. This
    schema is the transport shape of a report that already satisfies it.
    """

    surfaced: list[str] = []
    confidently_excluded: list[str] = []
    advised: list[OverviewAdvisedObligationPayload] = []
    out_of_scope: list[str] = []


class OverviewCalendarProfilePayload(OutputSchema):
    """One profile's calendar SUMMARY in ``overview calendar --all-profiles`` mode.

    Counts and the next obligation due, not the profile's whole calendar: the
    survey answers which profile needs attention, and the detail is one
    per-profile call away. The text surface still prints every row.

    ``next_due_*`` is the earliest obligation closing at or after the queried
    window's start, absent when the profile has none in range.
    """

    profile_id: ProfileId
    label: str
    entry_count: int
    event_count: int
    warning_count: int
    suppressed_entry_count: int
    next_due_modelo: str | None = None
    next_due_period: str | None = None
    next_due_closes_on: str | None = None


# ---------------------------------------------------------------------------
# Graph-declared schema targets
# ---------------------------------------------------------------------------


class OverviewStatusResult(OutputSchema):
    """JSON envelope result for ``aeat app overview status``.

    The full-status branch accepts the JSON form of
    :class:`OverviewStatusReport`; the period branch uses
    :class:`OverviewDraftPayload` rows derived from matching
    :class:`ModeloDraft` records for the scoped draft list. The application
    report is derived from :class:`OperatorStateProjection`; this schema only
    bounds the CLI envelope branch and permits future report fields through
    ``extra='allow'``.
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
    model_config = {"extra": "allow"}  # type: ignore[assignment]  # reason: Full status-report passthrough (model_dump of OverviewStatusReport). The status report is an application-layer pydantic model; the full shape is fo...


class OverviewCalendarResult(OutputSchema):
    """JSON envelope for ``aeat app overview calendar``.

    Covers both the compact single-profile mode (actionable deadline/event
    summaries plus warnings and coverage) and the ``--all-profiles`` survey
    mode (``profiles`` populated, single-profile fields empty). The same
    envelope key serves the leaf so the JSON-contract registry holds exactly
    one schema per CLI leaf; the populated field set identifies the branch.
    """

    from_date: str | None = None
    to_date: str | None = None
    range: OverviewCalendarRangePayload | None = None
    entries: list[OverviewCalendarEntrySummaryPayload] = []
    events: list[OverviewCalendarEventSummaryPayload] = []
    warnings: list[OverviewCalendarWarningPayload] = []
    generated_at: str | None = None
    completeness: OverviewCalendarCompletenessPayload | None = None
    taxpayer_model_declared: bool | None = None
    incomplete_reason: str | None = None
    suppressed_entries: list[OverviewSuppressedCalendarEntryPayload] = []
    profiles: list[OverviewCalendarProfilePayload] = []
    coverage: OverviewObligationCoveragePayload | None = None

    @model_validator(mode="after")
    def _require_single_profile_coverage(self) -> Self:
        if self.range is not None and self.coverage is None:
            raise ValueError("single-profile calendar results must include obligation coverage")
        return self


class OverviewAgendaResult(OutputSchema):
    """JSON envelope result for ``aeat app overview agenda``.

    Accepts the JSON form of :class:`OverviewAgenda` so the application read
    model remains the payload authority. That model reuses
    :class:`OverviewCalendarEntry`, :class:`CalendarWarning`, and
    :class:`CalendarCompleteness` rows from the calendar build.
    """

    as_of: str | None = None
    horizon_days: int | None = None
    coverage: OverviewObligationCoveragePayload
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]  # reason: TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR: pydantic v2 model_config class-variable assignment triggers mypy [assignment]; suppression is...


class OverviewBacklogResult(OutputSchema):
    """JSON envelope result for ``aeat app overview backlog``.

    Accepts the JSON form of :class:`OverviewBacklog` while the CLI controls
    only graph-derived envelope selection and rendering. The backlog read model is a
    filtered :class:`OverviewCalendar` projection, so its items remain calendar
    entry rows rather than command-local DTOs.
    """

    coverage: OverviewObligationCoveragePayload
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]  # reason: TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR: pydantic v2 model_config class-variable assignment triggers mypy [assignment]; suppression is...


class OverviewExplainResult(OutputSchema):
    """JSON envelope result for ``aeat app overview explain``.

    Accepts the JSON form of :class:`OverviewExplain`, including the
    applicability verdict, legal references, and profile facts. The verdict is
    the registry-grounded :class:`ApplicabilityVerdict`, not a deadline-window
    guess made by the CLI.
    """

    modelo: str | None = None
    year: int | None = None
    applicable: bool | None = None
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]  # reason: TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR: pydantic v2 model_config class-variable assignment triggers mypy [assignment]; suppression is...


class OverviewPrepareStepPayload(OutputSchema):
    """One ordered row in the ``aeat app overview prepare`` checklist.

    Mirrors :class:`~cadrumo.application.overview.DataPrepStep`: a closed step
    identifier, its current readiness state, a human-readable progress summary,
    and the schema-resolved action that advances the step.

    ``next_action`` is absent when the continuation needs operator-supplied
    input this read model cannot know. That is stated by omission rather than by
    a placeholder command, and it never means the step is finished - read
    ``state`` for that.
    """

    step_id: DataPrepStepId
    state: DataPrepStepState
    summary: str
    next_action: ResolvedNoticeAction | None = None


class OverviewPrepareResult(OutputSchema):
    """JSON envelope result for ``aeat app overview prepare``.

    Wraps :class:`~cadrumo.application.overview.DataPrepWalkthrough`: the ordered
    data-prep checklist for one ``(modelo, filing_year, period)`` scope,
    read-only over the active profile bucket's ledger, invoice, evidence, and
    modelo work-unit state. Never contacts AEAT and persists nothing.
    """

    modelo: str
    filing_year: int
    period: str
    steps: list[OverviewPrepareStepPayload] = []
    ready_for_calculation: bool = False


class OverviewPipelineModeloPayload(OutputSchema):
    """One modelo readiness row nested in a pipeline health result.

    Mirrors :class:`~cadrumo.application.overview.ModeloHealthRow`: the modelo's
    current readiness state against the requested period, its outstanding
    blocking/warning finding counts, and the schema-resolved action that
    advances it.
    """

    modelo: str
    work_unit_id: WorkUnitId | None = None
    state: ModeloReadinessState
    blocking_finding_count: NonNegativeInt = 0
    warning_finding_count: NonNegativeInt = 0
    summary: str
    next_action: ResolvedNoticeAction | None = None


class OverviewPipelineResult(OutputSchema):
    """JSON envelope result for ``aeat app overview pipeline``.

    Wraps :class:`~cadrumo.application.overview.PipelineHealthReport`: the
    cross-domain pipeline health dashboard for one ``(filing_year, period)``
    scope, composing the reused ledger status report, one modelo readiness
    row per work unit found for the period, and aggregate finding counts.
    Read-only over the active profile bucket's ledger, modelo work-unit,
    calculation-revision, and verification-report state. Never contacts
    AEAT and persists nothing.
    """

    filing_year: int
    period: str
    ledger: LedgerStatusResult
    modelos: list[OverviewPipelineModeloPayload] = []
    total_blocking_findings: int = 0
    total_warning_findings: int = 0
    ready: bool = False
