"""Typed ``--json`` payload schemas for modelo command envelopes.

Each command result is a strict
:class:`OutputSchema` subclass referenced by
production-authored CommandSpec as deferred public schema targets for a stable command path
and wrapped at emit time in
:class:`SchemaEnvelope` through
:func:`emit_envelope`. This file is the CLI-side
projection boundary for :mod:`modelo`: application and domain
results stay authoritative while these classes expose JSON-safe
:class:`WorkUnit`,
:class:`CalculationRevision`,
:class:`ModeloRecord`,
:class:`VerificationReport`,
:obj:`CasillaId`,
:obj:`LegalRefId`, and
:obj:`SourceRefId` fields to operators.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import ConfigDict, Field, NonNegativeInt, computed_field, model_validator

from ...application.calculations.observations_repository import (
    ObservationSourceKind,
)
from ...application.modelo.calculation_report_export import ModeloCalculationReportResult
from ...application.modelo.calculation_report_verification import (
    CalculationSummaryCheckName,
    CalculationSummaryVerification,
    CalculationSummaryVerificationLayer,
    CalculationSummaryVerificationOutcome,
    CalculationSummaryVerificationReason,
)
from ...application.modelo.historical_filing_projection import ModeloHistoricalFilingContentProjection
from ...application.modelo.result_summary_payload import ResultSummaryRowPayload
from ...application.modelo.work_plazo import validate_modelo_work_deadline_posture
from ...application.modelo.work_review import (
    BlockerRef,
    ModeloWorkProgress,
    ModeloWorkReview,
)
from ...core.calculation_report_format import CalculationReportDocumentFormat
from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId, VerificationReportId, WorkUnitId
from ...core.json_contract import OutputSchema, ResolvedPreconditionAction
from ...core.period import Period
from ...core.prose_elision import elided_prose
from ...core.text_bounds import NonEmptyStr
from ...core.time.utc import UtcInstant
from ...domain.calculations.registry.ids import (
    BindingId,
    LegalRefId,
    RelationId,
    RevisionId,
    SourceRefId,
    VerificationExpectationId,
)
from ...domain.calculations.registry.schema_base import LegalRefs
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.deadlines.festivos import DeadlineHolidayCoverage
from ...domain.filing.software_identity import AeatSoftwareIdentityGrade
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.calculation_revision_amendment import M303RectificativaMotive
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecordStatus,
)
from ...domain.modelos.filing_text import EvidenceReference, FilingNotes, ModeloActorLabel
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ._decimal_wire import DecimalWireText
from ._filing_chain_payloads import (
    AeatRegisterRefPayload,
    FilingReconciliationPayload,
    ObservationLayersPayload,
)
from ._modelo_revision_payload_parts import (
    CalculationRevisionProjectionFields,
    DetailRowPayload,
    ObservationPayload,
    SourceProvenancePayload,
)

if TYPE_CHECKING:
    pass


class WorkUnitPayload(OutputSchema):
    """Shared JSON projection of a bucket-scoped :class:`WorkUnit`.

    Built by :func:`work_unit_payload`.
    The payload carries the stable
    :obj:`WorkUnitId`, operator-facing short ids,
    current / filed
    :obj:`CalculationRevisionId` pointers, optional
    :obj:`FilingRecordId`, and discard metadata used
    by create, list, status, rename, and discard lifecycle commands. It is
    lifecycle metadata only: calculation, verification, filing, and import
    evidence remain in their own command payloads.
    """

    work_unit_id: WorkUnitId
    short_work_unit_id: str
    bucket_id: BucketId
    modelo: str
    filing_year: int
    period: Period
    revision_id: RevisionId
    name: str
    state: str
    current_calculation_revision_id: CalculationRevisionId | None = None
    short_current_calculation_revision_id: str | None = None
    filed_calculation_revision_id: CalculationRevisionId | None = None
    short_filed_calculation_revision_id: str | None = None
    current_filing_record_id: FilingRecordId | None = None
    created_at: str
    updated_at: str
    discarded_at: str | None = None
    discarded_by: str | None = None
    discard_reason: str | None = None
    causante_ccaa: str | None = None


class WorkConditionalRecargoPreviewPayload(OutputSchema):
    """Explicitly unassessed Article 27 rate preview for an overdue deadline.

    The rate is derived from the governed deadline table at
    ``rate_reference_on``. It reports neither a filing presentation date nor a
    determination that the filing owes a surcharge or interest. The literal
    status keeps this calculate-time contract fail-closed until a future
    provenance-bearing Article 27 assessment boundary exists.
    """

    band_id: str
    surcharge_pct: str  # serialised Decimal
    interest_applies: bool
    legal_ref: str
    rate_reference_on: str  # ISO date, not an actual presentation date
    assessment_status: Literal["unassessed"] = "unassessed"


class WorkDeadlinePosturePayload(OutputSchema):
    """Filing-deadline (plazo voluntario) state for the work unit.

    Structured result data the calculate verb exists to surface: the
    effective voluntary-filing close date (after the business-day shift), the
    nominal close date the deadline window declares, which holidays the
    effective date accounts for, and the in-time / overdue posture counted
    against the effective date. When overdue, it can carry an explicitly
    unassessed conditional Article 27 rate preview. It never asserts surcharge
    or interest liability. Distinct from the non-blocking advisory prose, which
    rides the envelope ``notices`` channel.
    """

    closes_on: date
    nominal_closes_on: date
    holiday_coverage: DeadlineHolidayCoverage
    days_remaining: int | None = None
    days_overdue: int | None = None
    conditional_recargo_preview: WorkConditionalRecargoPreviewPayload | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_deadline_posture(self) -> WorkDeadlinePosturePayload:
        """Reuse the application deadline state invariant at the JSON boundary."""
        validate_modelo_work_deadline_posture(
            closes_on=self.closes_on,
            nominal_closes_on=self.nominal_closes_on,
            days_remaining=self.days_remaining,
            days_overdue=self.days_overdue,
        )
        return self


class CalculationRevisionPayload(OutputSchema):
    """Shared JSON projection of a persisted :class:`CalculationRevision`.

    Built by
    :func:`~cadrumo.entrypoints.cli.operation_modelo_calculation.calculation_snapshot_payload`.
    ``casilla_values`` is the flat convenience table keyed by
    :obj:`CasillaId`, while
    ``observations`` carries joinable :class:`ObservationPayload` rows projected
    from :class:`CasillaObservation`.
    ``result_summary`` carries :class:`ResultSummaryRowPayload` rows selected
    from :class:`ResultSummaryRow`. ``source_provenance`` carries
    :class:`SourceProvenancePayload` rows projected from
    :class:`CalculationSourceRef`, including each carry's declared
    ``dependency_treatment``. The binding and
    relation override maps preserve the operator inputs that shaped the draft
    revision.
    """

    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    registry_snapshot_ref: RegistrySnapshotRef
    state: str
    casilla_values: dict[CasillaId, str]  # casilla_id -> str(Decimal)
    observations: tuple[ObservationPayload, ...]
    result_summary: tuple[ResultSummaryRowPayload, ...] = ()
    detail_rows: tuple[DetailRowPayload, ...] = ()
    source_provenance: tuple[SourceProvenancePayload, ...] = ()
    binding_overrides: dict[BindingId, str]
    relation_overrides: dict[RelationId, str] = Field(default_factory=dict)
    input_values_by_casilla_id: dict[CasillaId, str]
    created_at: str
    updated_at: str
    verified_at: str | None = None
    verified_by: str | None = None
    filed_at: str | None = None
    filed_by: str | None = None
    superseded_at: str | None = None


#: Longest rendered verification-finding message the wire carries.
FINDING_MESSAGE_CAP = 500

if TYPE_CHECKING:
    #: A rendered finding message, elided at the cap rather than refused. The
    #: runtime annotation below carries the cap as a real pydantic constraint;
    #: the checker only needs to know the field is text.
    type FindingMessage = str
else:
    FindingMessage = elided_prose(FINDING_MESSAGE_CAP)


class FindingPayload(OutputSchema):
    """One localized verification finding with its resolved recovery verdict.

    Persisted findings remain factual audit records.  A live verification can
    additionally attach the schema-resolved precondition verdict produced by
    the application service; historical report reads deliberately leave it
    absent rather than reconstructing recovery advice from finding prose.
    """

    kind: ModeloVerificationFindingKind
    severity: ModeloVerificationFindingSeverity
    casilla_id: CasillaId | None = None
    expectation_id: VerificationExpectationId | None = None
    # Elides rather than refuses, because this message is not authored: it is
    # ``tr(finding.message_locale_key, **finding.message_facts)``, a template
    # with taxpayer data substituted, so its length is set by the household. A
    # hard cap turns the longest findings -- the ones with most to say -- into a
    # refused payload, which drops the finding rather than shortening it.
    message: FindingMessage
    action: ResolvedPreconditionAction | None = None
    legal_refs: LegalRefs
    source_refs: list[SourceRefId] = Field(default_factory=list)


class CrossPeriodDependencyRequirementPayload(OutputSchema):
    """One upstream filing dependency declared by the registry.

    Mirrors :class:`~application.calculations.cross_period_models.CrossPeriodDependencyRequirement`.
    ``legal_refs`` and ``source_refs`` are carried unbounded (no
    ``min_length=1`` restated) because the sole construction site,
    ``_dependency_inventory_item_payload`` in
    :mod:`~cadrumo.entrypoints.cli._modelo_work_verification_cli`, builds this
    payload field-by-field from an already-validated
    ``CrossPeriodDependencyRequirement`` instance, whose own ``Field(min_length=1)``
    on both fields already guarantees non-emptiness; no path builds this payload
    from raw JSON, a dict, or a partial reconstruction, so restating the bound
    here would be redundant rather than protective.

    ``required_source_casilla_ids`` and ``source_presence_groups`` are carried for
    the same reason ``legal_refs``/``source_refs`` are: an operator reading
    ``source_casilla_ids`` alone cannot tell a dependency requiring every listed
    casilla from one where only a mandatory subset is required and the rest are
    OR-alternatives grouped in ``source_presence_groups`` — omitting them
    overstates the dependency's rigidity.
    """

    source_modelo: str
    filing_year: int
    period: Period
    source_casilla_ids: tuple[CasillaId, ...]
    required_source_casilla_ids: tuple[CasillaId, ...] | None = None
    source_presence_groups: tuple[tuple[CasillaId, ...], ...] = ()
    origin: str
    origin_ids: tuple[str, ...]
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]
    requires_member_fan_in: bool


class CrossPeriodDependencyInventoryItemPayload(OutputSchema):
    """One target filing that requires clean upstream filing history."""

    target_modelo: str
    target_revision_id: RevisionId
    target_filing_year: int
    target_period: Period
    dependency_count: int
    source_modelos: tuple[str, ...]
    dependencies: tuple[CrossPeriodDependencyRequirementPayload, ...]


class CrossPeriodDependencyEvidencePayload(OutputSchema):
    """Current clean-state evidence for one dependency requirement."""

    source_modelo: str
    filing_year: int
    period: Period
    clean: bool
    blockers: tuple[str, ...]
    observation_source_kind: str | None = None
    filing_record_id: FilingRecordId | None = None
    calculation_revision_id: CalculationRevisionId | None = None
    external_evidence_kind: str | None = None
    expected_member_nifs: tuple[str, ...] = ()
    observed_member_nifs: tuple[str, ...] = ()
    missing_member_nifs: tuple[str, ...] = ()
    unexpected_member_nifs: tuple[str, ...] = ()


class CrossPeriodCleanStatePayload(OutputSchema):
    """Clean-state verdict for one target filing."""

    target_modelo: str
    target_filing_year: int
    target_period: Period
    requires_clean_state: bool
    clean: bool
    blockers: tuple[str, ...]
    dependencies: tuple[CrossPeriodDependencyEvidencePayload, ...]


class VerificationReportPayload(OutputSchema):
    """Shared projection of a :class:`VerificationReport`.

    ``findings`` carries the blocking or advisory
    :class:`FindingPayload` rows that
    explain whether the selected
    :class:`CalculationRevision` earned the
    verified-complete transition.

    The report's own invariants — the content-addressed id derivation, the
    bidirectional ``granted_verificado_completo`` rule, and the aware-instant
    check on ``run_at`` — are enforced on
    :class:`VerificationReport` and are not
    restated here. They cannot be: this projection renders each finding into
    localised prose, and the derivation hashes the locale-neutral finding
    identity that rendering replaces, so a payload could not recompute the id
    it carries even if it tried.
    """

    verification_report_id: VerificationReportId
    calculation_revision_id: CalculationRevisionId
    registry_snapshot_ref: RegistrySnapshotRef
    completeness_status: VerificationCompletenessStatus
    granted_verificado_completo: bool
    resolved_casilla_ids: list[CasillaId]
    missing_required_casilla_ids: list[CasillaId]
    run_at: str
    verified_by: str
    findings: list[FindingPayload]


class ExternalEvidencePayload(OutputSchema):
    """JSON projection of :class:`ExternalEvidence`.

    The evidence reference records the official AEAT source consumed by
    :func:`import_external_filing_evidence`; it is data
    observed outside the application, not proof that this CLI submitted the return.
    """

    kind: ExternalEvidenceKind
    reference_id: EvidenceReference
    imported_at: datetime


class ModeloRecordPayload(OutputSchema):
    """Shared projection of a :class:`ModeloRecord`.

    The payload represents local filing state for a verified
    :class:`CalculationRevision`; it is not a live AEAT
    submission. Evidence appears only through ``external_evidence``.
    """

    filing_record_id: FilingRecordId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    bucket_id: BucketId
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    filed_at: UtcInstant
    filed_by: ModeloActorLabel
    member_nif: str | None = None
    notes: FilingNotes | None = None
    origin: FilingOrigin
    confirmation: AeatConfirmationState
    declaration_kind: FilingDeclarationKind
    aeat_register: AeatRegisterRefPayload | None = None
    aeat_accepted: bool = False
    status: ModeloRecordStatus
    superseded_at: datetime | None = None
    superseded_by_filing_record_id: FilingRecordId | None = None
    external_evidence: ExternalEvidencePayload | None = None
    amends_filing_record_id: FilingRecordId | None = None
    kind: Literal["internal_filing"] = "internal_filing"
    live_submission: bool = False

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_filing_record_grounding(self) -> ModeloRecordPayload:
        """Keep the JSON projection aligned with the filing-record invariant."""
        if self.aeat_accepted != (self.confirmation is AeatConfirmationState.CONFIRMADA):
            raise ValueError("AEAT acceptance must follow the confirmation state")
        if self.aeat_accepted != (self.external_evidence is not None):
            raise ValueError("AEAT acceptance and external evidence must be supplied together")
        if self.status is ModeloRecordStatus.VIGENTE:
            if self.superseded_at is not None or self.superseded_by_filing_record_id is not None:
                raise ValueError("current filing record must not carry supersession metadata")
        elif self.superseded_at is None or self.superseded_by_filing_record_id is None:
            raise ValueError("superseded filing record must carry supersession metadata")
        elif self.superseded_at < self.filed_at:
            raise ValueError("superseded_at must not precede filed_at")
        return self


class WorkCreateResult(OutputSchema):
    """Creation result returned by ``aeat app modelo work create``.

    Mirrors :class:`WorkUnitPayload` after the application/modelo lifecycle
    service resolves the registry revision and active bucket profile, then adds
    create-specific status fields such as ``name_applied`` and
    ``applicability_guard_bypassed``. Newly created work units have no current
    :class:`CalculationRevision` or filing record until
    later lifecycle commands populate those pointers.
    """

    operation: str = "modelo.work.create"
    status: str
    status_message: str
    name_applied: str | None = None
    applicability_guard_bypassed: bool
    work_unit_id: WorkUnitId
    short_work_unit_id: str
    bucket_id: BucketId
    modelo: str
    filing_year: int
    period: Period
    revision_id: RevisionId
    name: str
    state: str
    current_calculation_revision_id: CalculationRevisionId | None = None
    short_current_calculation_revision_id: str | None = None
    filed_calculation_revision_id: CalculationRevisionId | None = None
    short_filed_calculation_revision_id: str | None = None
    current_filing_record_id: FilingRecordId | None = None
    created_at: str
    updated_at: str
    discarded_at: str | None = None
    discarded_by: str | None = None
    discard_reason: str | None = None
    causante_ccaa: str | None = None


class WorkListResult(OutputSchema):
    """Work-unit listing result returned by ``aeat app modelo work list``.

    The list contains :class:`WorkUnitPayload` rows for the selected bucket and
    filters.  Discarded work units stay preserved in storage for audit history
    but are omitted unless ``include_discarded`` is true.
    """

    operation: str = "modelo.work.list"
    bucket_id_filter: str | None = None
    include_discarded: bool
    work_unit_count: int
    work_units: list[WorkUnitPayload]


class WorkSelectResult(OutputSchema):
    """Work-unit list result returned by ``aeat app modelo work select``."""

    operation: str = "modelo.work.select"
    bucket_id_filter: str | None = None
    include_discarded: bool
    work_unit_count: int
    work_units: list[WorkUnitPayload]


class WorkStatusResult(OutputSchema):
    """Status projection returned by ``aeat app modelo work status``.

    Reports one :class:`WorkUnit` lifecycle root together
    with the current calculation, filed calculation, and filing-record pointers
    that default downstream work-unit commands. It does not inline the referenced
    calculation, verification, or filing payloads.
    """

    operation: str = "modelo.work.status"
    work_unit_id: WorkUnitId
    short_work_unit_id: str
    bucket_id: BucketId
    modelo: str
    filing_year: int
    period: Period
    revision_id: RevisionId
    name: str
    state: str
    current_calculation_revision_id: CalculationRevisionId | None = None
    short_current_calculation_revision_id: str | None = None
    filed_calculation_revision_id: CalculationRevisionId | None = None
    short_filed_calculation_revision_id: str | None = None
    current_filing_record_id: FilingRecordId | None = None
    created_at: str
    updated_at: str
    discarded_at: str | None = None
    discarded_by: str | None = None
    discard_reason: str | None = None
    causante_ccaa: str | None = None


class WorkRenameResult(OutputSchema):
    """Rename confirmation returned by ``aeat app modelo work rename``.

    A rename preserves the :obj:`WorkUnitId`, registry
    revision, and stored calculation / filing pointers while updating only
    display metadata and ``updated_at``. Discarded work units are rejected before
    this payload is emitted.
    """

    operation: str = "modelo.work.rename"
    work_unit_id: WorkUnitId
    short_work_unit_id: str
    bucket_id: BucketId
    modelo: str
    filing_year: int
    period: Period
    revision_id: RevisionId
    name: str
    state: str
    current_calculation_revision_id: CalculationRevisionId | None = None
    short_current_calculation_revision_id: str | None = None
    filed_calculation_revision_id: CalculationRevisionId | None = None
    short_filed_calculation_revision_id: str | None = None
    current_filing_record_id: FilingRecordId | None = None
    created_at: str
    updated_at: str
    discarded_at: str | None = None
    discarded_by: str | None = None
    discard_reason: str | None = None
    causante_ccaa: str | None = None


class WorkDiscardResult(OutputSchema):
    """Work-unit discard confirmation returned by ``aeat app modelo work discard``.

    The discard is an audit-grade transition on the
    :class:`WorkUnit` lifecycle root: the record is
    preserved with ``discarded_at`` / ``discarded_by`` / ``discard_reason``
    populated, default listings hide it, and subsequent mutations are rejected.
    It never deletes the stored calculation revisions or contacts AEAT.
    """

    operation: str = "modelo.work.discard"
    work_unit_id: WorkUnitId
    short_work_unit_id: str
    bucket_id: BucketId
    modelo: str
    filing_year: int
    period: Period
    revision_id: RevisionId
    name: str
    state: str
    current_calculation_revision_id: CalculationRevisionId | None = None
    short_current_calculation_revision_id: str | None = None
    filed_calculation_revision_id: CalculationRevisionId | None = None
    short_filed_calculation_revision_id: str | None = None
    current_filing_record_id: FilingRecordId | None = None
    created_at: str
    updated_at: str
    discarded_at: str | None = None
    discarded_by: str | None = None
    discard_reason: str | None = None
    causante_ccaa: str | None = None


class WorkCalculateResult(CalculationRevisionProjectionFields):
    """Successful ``modelo work calculate`` result payload.

    The calculate CLI flattens the persisted
    :class:`CalculationRevision` fields from
    :class:`CalculationRevisionPayload`
    (carried by the full shared revision projection base),
    then adds the presentation-only values
    carried by
    :class:`ModeloWorkCalculationServiceResult`: Modelo
    202 modality, backend authorization state, and optional
    :class:`WorkDeadlinePosturePayload`.
    Non-blocking authorization and source diagnostics are projected into the envelope's
    :class:`Notice` rows, not bespoke result fields.
    """

    operation: str = "modelo.work.calculate"
    saved: bool = True
    saved_confirmation: str
    modality: str | None = None
    modality_reason: str | None = None
    authorization_state: str | None = None
    deadline: WorkDeadlinePosturePayload | None = None


class M303Exonerado390AttestationResult(OutputSchema):
    """Sanitized secure-reference result of ordinary M303 applicability admission."""

    operation: str = "modelo.work.attest-m303-exonerado-390"
    filing_year: int
    period: Period
    attachment_id: str
    sha256: str


class CalculationRevisionSummaryPayload(OutputSchema):
    """Compact calculation-revision row returned by ``modelo.work.revisions``."""

    short_calculation_revision_id: str
    calculation_revision_id: CalculationRevisionId
    short_work_unit_id: str
    work_unit_id: WorkUnitId
    state: CalculationRevisionState
    created_at: str


class WorkRevisionsResult(OutputSchema):
    """Calculation-revision listing returned by ``aeat app modelo work revisions``.

    Each entry is a compact discovery row. Resolve its
    ``calculation_revision_id`` through ``modelo.work.revision`` for the full
    casilla table, typed observations, and provenance.
    """

    operation: str = "modelo.work.revisions"
    work_unit_id_filter: str | None = None
    revision_count: int
    revisions: list[CalculationRevisionSummaryPayload]


class WorkVerifyResult(OutputSchema):
    """Verification report returned by ``aeat app modelo work verify``.

    The command delegates to
    :func:`verify_modelo_revision_with_preconditions` and returns the
    resulting
    :class:`VerificationReportPayload`.
    On a successful
    verificado-completo verdict the revision transitions to
    ``verificado_completo``; on a refused verdict the revision is unchanged and
    ``findings`` names every blocking or advisory issue. Advisory findings also
    ride the envelope's :class:`Notice` channel.
    """

    operation: str = "modelo.work.verify"
    verification_report_id: VerificationReportId
    calculation_revision_id: CalculationRevisionId
    registry_snapshot_ref: RegistrySnapshotRef
    completeness_status: VerificationCompletenessStatus
    granted_verificado_completo: bool
    resolved_casilla_ids: list[CasillaId]
    missing_required_casilla_ids: list[CasillaId]
    run_at: str
    verified_by: str
    findings: list[FindingPayload]


class WorkReviewPayload(OutputSchema):
    """Compact CLI projection of current review state.

    Full casilla values and source provenance remain available through the
    persisted calculation revision read. This derived review keeps lifecycle,
    progress, actionable findings and blockers, plus counts that make omitted
    detail explicit.
    """

    # Annotated as `ConfigDict` so the literal is checked against the TypedDict.
    # A bare `ConfigDict(**{**base, "key": value})` collapses every value to
    # `object | bool` and mistyped all 48 keys; passing the keyword alongside
    # `**base` instead makes the checker suspect a duplicate it cannot rule out.
    model_config: ClassVar[ConfigDict] = {**OutputSchema.model_config, "hide_input_in_errors": True}
    bucket_id: BucketId
    modelo: ModeloCode
    filing_year: int
    period: Period
    registry_revision_id: RevisionId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId | None
    lifecycle_state: CalculationRevisionState | None
    verification_outcome: VerificationCompletenessStatus | None
    progress: ModeloWorkProgress
    casilla_count: NonNegativeInt
    findings: tuple[ModeloVerificationFinding, ...]
    blockers: tuple[BlockerRef, ...]
    row_source_fingerprint_count: NonNegativeInt

    @classmethod
    def from_review(cls, review: ModeloWorkReview) -> WorkReviewPayload:
        """Build the ordinary-output projection without secure identity state."""
        return cls(
            bucket_id=review.bucket_id,
            modelo=review.modelo,
            filing_year=review.filing_year,
            period=review.period,
            registry_revision_id=review.registry_revision_id,
            work_unit_id=review.work_unit_id,
            calculation_revision_id=review.calculation_revision_id,
            lifecycle_state=review.lifecycle_state,
            verification_outcome=review.verification_outcome,
            progress=review.progress,
            casilla_count=len(review.casillas),
            findings=review.findings,
            blockers=review.blockers,
            row_source_fingerprint_count=len(review.row_source_fingerprints),
        )


class WorkReportResult(OutputSchema):
    """JSON envelope for ``aeat app modelo work report``.

    Projects :class:`~cadrumo.application.modelo.calculation_report_export.ModeloCalculationReportResult`.
    The exported rows are in the file the operator chose; this payload carries the
    facts that identify it -- where it landed, how large it is, the digest of its
    bytes, and the digest of the report content those bytes render -- plus the
    traceability coordinates a reader joins back to the stored revision.

    ``report_sha256`` is the report's own canonical digest and is therefore equal
    for two documents rendering the same report, while ``file_sha256`` differs per
    serialisation.
    """

    operation: Literal["modelo.work.report"] = "modelo.work.report"
    modelo: str
    filing_year: int
    period: Period
    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    verification_report_id: VerificationReportId | None = None
    filing_record_id: FilingRecordId | None = None
    document_format: CalculationReportDocumentFormat
    report_language: OutputLanguage
    output_path: str
    byte_size: NonNegativeInt
    file_sha256: str
    report_sha256: str
    row_count: NonNegativeInt
    software_identity_grade: AeatSoftwareIdentityGrade | None = None
    local_calculation_notice: str
    #: Fingerprint of the profile key a summary PDF is certified with; ``None``
    #: for a document format that carries no signature.
    signing_key_fingerprint: str | None = None

    @classmethod
    def from_result(cls, result: ModeloCalculationReportResult) -> WorkReportResult:
        """Project the application receipt onto the JSON transport shape."""
        return cls(
            modelo=str(result.modelo),
            filing_year=int(result.filing_year),
            period=result.period,
            calculation_revision_id=result.calculation_revision_id,
            work_unit_id=result.work_unit_id,
            verification_report_id=result.verification_report_id,
            filing_record_id=result.filing_record_id,
            document_format=result.document_format,
            report_language=result.report_language,
            output_path=str(result.output_path),
            byte_size=result.byte_size,
            file_sha256=result.file_sha256,
            report_sha256=result.report_sha256,
            row_count=result.row_count,
            software_identity_grade=result.software_identity_grade,
            local_calculation_notice=result.local_calculation_notice,
            signing_key_fingerprint=result.signing_key_fingerprint,
        )


class WorkReportVerifyCheck(OutputSchema):
    """One check ``work report-verify`` ran, and the reason it reported, if any."""

    check: CalculationSummaryCheckName
    layer: CalculationSummaryVerificationLayer
    reason: CalculationSummaryVerificationReason | None = None
    detail: str | None = None
    refuses: bool


class WorkReportVerifyResult(OutputSchema):
    """JSON envelope for ``aeat app modelo work report-verify``.

    Projects :class:`~cadrumo.application.modelo.calculation_report_verification.CalculationSummaryVerification`.
    Carries the verdict, every check that ran and the identifiers the summary's
    signed statement names -- never a taxpayer figure or identity, which stay in
    the file being verified.
    """

    operation: Literal["modelo.work.report_verify"] = "modelo.work.report_verify"
    path: str
    outcome: CalculationSummaryVerificationOutcome
    store_checked: bool
    reasons: list[CalculationSummaryVerificationReason]
    checks: list[WorkReportVerifyCheck]
    calculation_revision_id: CalculationRevisionId | None = None
    report_sha256: str | None = None
    statement_sha256: str | None = None
    signing_key_fingerprint: str | None = None

    @classmethod
    def from_verification(cls, verification: CalculationSummaryVerification, *, path: object) -> WorkReportVerifyResult:
        """Project the application verdict onto the JSON transport shape."""
        return cls(
            path=str(path),
            outcome=verification.outcome,
            store_checked=verification.store_checked,
            reasons=list(verification.reasons),
            checks=[
                WorkReportVerifyCheck(
                    check=check.check,
                    layer=check.layer,
                    reason=check.reason,
                    detail=check.detail,
                    refuses=check.refuses,
                )
                for check in verification.checks
            ],
            calculation_revision_id=verification.calculation_revision_id,
            report_sha256=verification.report_sha256,
            statement_sha256=verification.statement_sha256,
            signing_key_fingerprint=verification.signing_key_fingerprint,
        )


class WorkReviewResult(OutputSchema):
    """Envelope payload carrying the canonical application review record.

    The CLI boundary uses an explicit safe projection so encrypted row-source
    identities cannot enter generic JSON serialization. Operator review keeps
    only their binding/row/source-kind/fingerprint cohort provenance.
    """

    operation: Literal["modelo.work.review"] = "modelo.work.review"
    review: WorkReviewPayload


class WorkDependenciesResult(OutputSchema):
    """Cross-period dependency inventory and optional active-bucket clean-state verdict."""

    operation: str = "modelo.work.dependencies"
    filing_year: int
    modelo_filter: str | None = None
    period_filter: str | None = None
    target_modelos: tuple[str, ...]
    source_modelos: tuple[str, ...]
    target_count: int
    items: tuple[CrossPeriodDependencyInventoryItemPayload, ...]
    clean_state: CrossPeriodCleanStatePayload | None = None


class WorkFileResult(ModeloRecordPayload):
    """Internal-filing confirmation returned by ``aeat app modelo work file``.

    The command delegates to
    :func:`file_modelo_revision` and returns the
    resulting :class:`ModeloRecordPayload`. It records that the verified
    revision was marked as internally filed. It does not attach
    :class:`ExternalEvidencePayload`; ``live_submission`` is always ``False``.
    """

    operation: str = "modelo.work.file"


class WorkAmendResult(ModeloRecordPayload):
    """Amendment filing confirmation returned by ``aeat app modelo work amend``.

    The command delegates to
    :func:`amend_modelo_revision` and returns the
    resulting :class:`ModeloRecordPayload` with the amendment-specific pair
    (``amendment_kind``, ``amends_filing_record_id``). The source filing record
    must carry :class:`ExternalEvidence`; the new filing
    record clears ``external_evidence`` and remains local, so ``live_submission``
    is always ``False``.
    """

    operation: str = "modelo.work.amend"
    amendment_kind: str
    m303_rectificativa_motive: M303RectificativaMotive | None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _amendment_names_the_record_it_supersedes(self) -> WorkAmendResult:
        """Refuse an amendment result that does not name the record it amends.

        The field stays optional in type because the shared record payload
        declares it that way for every non-amending result. An amendment
        without it is incomplete, so it is refused here rather than emitted.
        """
        if self.amends_filing_record_id is None:
            raise ValueError("an amendment result must carry amends_filing_record_id")
        return self


class ModeloRecordListResult(OutputSchema):
    """Filing-record listing returned by ``aeat app modelo filing-record list``."""

    operation: str = "modelo.filing_record.list"
    bucket_id_filter: str | None = None
    modelo_filter: str | None = None
    include_superseded: bool
    record_count: int
    records: list[ModeloRecordPayload]


class ModeloRecordShowResult(ModeloRecordPayload):
    """Filing-record detail returned by ``aeat app modelo filing-record view``.

    ``observation_layers`` shows the official and pending-local observations
    stored for the record's coordinate, and the audit of any operator override.
    """

    operation: str = "modelo.filing_record.show"
    observation_layers: ObservationLayersPayload
    historical_content: ModeloHistoricalFilingContentProjection


class VerificationReportListResult(OutputSchema):
    """Typed listing of persisted verification reports.

    ``reports`` contains shared
    :class:`VerificationReportPayload`
    projections; filtering only constrains ``calculation_revision_id_filter`` and
    leaves each report's finding, missing-casilla, and verificado-completo fields
    intact.
    """

    operation: str = "modelo.verification_report.list"
    calculation_revision_id_filter: str | None = None
    report_count: int
    reports: list[VerificationReportPayload]


class VerificationReportShowResult(OutputSchema):
    """Typed detail view for one persisted verification report.

    This schema mirrors :class:`WorkVerifyResult` verification fields so
    operators can re-read a saved
    :class:`VerificationReport` with the same
    :class:`FindingPayload`
    legal/source-reference detail emitted by
    ``aeat app modelo work verify``.
    """

    operation: str = "modelo.verification_report.show"
    verification_report_id: VerificationReportId
    calculation_revision_id: CalculationRevisionId
    registry_snapshot_ref: RegistrySnapshotRef
    completeness_status: VerificationCompletenessStatus
    granted_verificado_completo: bool
    resolved_casilla_ids: list[CasillaId]
    missing_required_casilla_ids: list[CasillaId]
    run_at: str
    verified_by: str
    findings: list[FindingPayload]


class FilingRecordImportResult(ModeloRecordPayload):
    """Result emitted by ``aeat app modelo filing-record import``.

    The command delegates to
    :func:`import_external_filing_evidence` and returns
    the resulting evidence-bearing :class:`ModeloRecordPayload` with
    :class:`ExternalEvidencePayload` data. Imported records are the
    :class:`ModeloRecord` baseline consumed by
    :func:`amend_modelo_revision`, not live submission.
    """

    operation: str = "modelo.filing_record.import"
    reconciliation: FilingReconciliationPayload

    @computed_field
    @property
    def evidence_kind(self) -> ExternalEvidenceKind:
        """The imported evidence's kind, READ from the evidence rather than declared.

        These two were accepted as their own input fields beside
        ``external_evidence``, which already carries both, and a validator
        checked the three agreed. Deriving them retires that check by making the
        disagreement unconstructible: there is now one place the kind and the
        reference come from, so a payload cannot state one thing in a flat field
        and another in the evidence row it projects.

        The wire shape is unchanged -- ``computed_field`` still emits them --
        so this removes an input duplication without moving the envelope.
        """
        if self.external_evidence is None:
            raise ValueError("imported filing record must carry external evidence")
        return self.external_evidence.kind

    @computed_field
    @property
    def evidence_reference_id(self) -> EvidenceReference:
        """The imported evidence's reference, read from the evidence row."""
        if self.external_evidence is None:
            raise ValueError("imported filing record must carry external evidence")
        return self.external_evidence.reference_id

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_external_evidence(self) -> FilingRecordImportResult:
        """An imported filing record carries the evidence it was imported from.

        All that remains of a validator that also checked ``evidence_kind`` and
        ``evidence_reference_id`` agreed with it. Those are derived from this
        field now, so they cannot disagree with it; what is still worth
        asserting is that the field is there at all, because an import without
        evidence is not an import.
        """
        if self.external_evidence is None:
            raise ValueError("imported filing record must carry external evidence")
        return self


class FilingRecordLocalObservationResult(OutputSchema):
    """Result emitted by ``aeat app modelo filing-record observe-local``.

    ``action`` says whether the operator recorded a pending-local override or
    cleared one. A recorded override mirrors
    :class:`ModeloLocalObservationResult`; a clear carries no values.
    ``observation_layers`` is the coordinate's state after the write, so the
    override audit and any official layer it sits above stay visible.
    ``official_evidence``, ``filing_record_created``, and ``aeat_accepted``
    are pinned ``False``: this command never stamps a ``ModeloRecord`` or
    :class:`ExternalEvidence`, so the envelope cannot be constructed to look
    like AEAT-backed evidence.
    """

    operation: str = "modelo.filing_record.observe_local"
    action: Literal["recorded", "cleared"]
    modelo: str
    filing_year: int
    period: Period
    revision_id: RevisionId | None = None
    observation_key: str
    source_kind: ObservationSourceKind | None = None
    casilla_values: dict[CasillaId, DecimalWireText] = {}
    casilla_count: NonNegativeInt = 0
    captured_at: datetime
    captured_by: NonEmptyStr
    reason: NonEmptyStr
    observation_layers: ObservationLayersPayload
    official_evidence: Literal[False] = False
    filing_record_created: Literal[False] = False
    aeat_accepted: Literal[False] = False

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_action_shape(self) -> FilingRecordLocalObservationResult:
        """Check the projected halves agree, reading which outcome carries detail from the application.

        Whether an outcome carries the observation's own detail is the
        application's statement, taken from
        ``LOCAL_OBSERVATION_ACTION_CARRIES_DETAIL``; this only asks that the
        wire row agrees with it, and that the count matches the values it sends.
        """
        from ...application.modelo.local_observation_actions import LOCAL_OBSERVATION_ACTION_CARRIES_DETAIL

        carries_detail = LOCAL_OBSERVATION_ACTION_CARRIES_DETAIL[self.action]
        stated = (self.revision_id is not None, self.source_kind is not None, bool(self.casilla_values))
        if any(state is not carries_detail for state in stated):
            raise ValueError(
                "a local observation states its revision, source kind and values exactly when it records them"
            )
        if self.casilla_count != len(self.casilla_values):
            raise ValueError("casilla_count must equal the number of casilla values")
        return self
