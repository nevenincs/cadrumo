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

from collections.abc import Sequence
from datetime import date, datetime
from typing import TYPE_CHECKING, Literal

from pydantic import ConfigDict, Field, NonNegativeInt, computed_field, field_validator, model_validator

from ...application.aggregation import (
    PerModeloAggregationContributor,
    PerModeloAggregationResult,
)
from ...application.calculations.observations_repository import (
    ObservationSourceKind,
    PriorDomiciliationElectionProjection,
)
from ...application.modelo.work_plazo import validate_modelo_work_deadline_posture
from ...application.modelo.work_review import (
    BlockerRef,
    ModeloWorkProgress,
    ModeloWorkReview,
)
from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.filing_year import FilingYear
from ...core.identity import (
    BucketId,
    CalculationRevisionId,
    FilingRecordId,
    ProfileId,
    TransactionId,
    VerificationReportId,
    WorkUnitId,
)
from ...core.json_contract import OutputSchema, ResolvedPreconditionAction
from ...core.payment_election import PaymentElection
from ...core.period import Period
from ...core.prose_elision import IssueDetail, elided_prose
from ...core.refund_election import RefundElection
from ...core.result_disposition import ResultDisposition
from ...core.text_bounds import NonEmptyStr
from ...core.time.utc import UtcInstant
from ...domain.buckets.event import (
    BucketActorLabel,
    BucketEventId,
    BucketEventObjectType,
    BucketEventType,
    BucketObjectId,
)
from ...domain.calculations.registry.ids import (
    BindingId,
    FormulaId,
    LegalRefId,
    ParameterId,
    RelationId,
    RevisionId,
    SourceRefId,
    VerificationExpectationId,
)
from ...domain.calculations.registry.schema_base import LegalRefs, SourceRefs
from ...domain.calculations.registry.withholding_bindings import WithholdingClaveBreakdown
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.calculation_revision_amendment import M303RectificativaMotive
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.filing_record import ExternalEvidenceKind, ModeloRecordStatus
from ...domain.modelos.filing_text import EvidenceReference, FilingNotes, ModeloActorLabel
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ._decimal_wire import DecimalWireText
from ._modelo_bindings_payloads import (
    BindingEncodedOptionPayload,
    BindingListRowPayload,
    BindingPreviewRowPayload,
    ModeloBindingsListResult,
    ModeloBindingsPreviewResult,
)
from ._modelo_iva_wallet_payloads import (
    IvaWalletBalanceResult,
    IvaWalletOverrideResult,
    IvaWalletSeedResult,
)
from ._modelo_revision_payload_parts import (
    CalculationRevisionCommandProjectionFields,
    DetailRowPayload,
    ObservationPayload,
    ResultSummaryRowPayload,
    SourceProvenancePayload,
)
from ._modelo_support_matrix_payloads import (
    ModeloPortalCompatibilityRefPayload,
    ModeloRenamePayload,
    ModeloSupportMatrixEntryPayload,
    ModeloSupportMatrixResult,
)
from ._modelo_work_revision_payloads import WorkObservationsResult, WorkRevisionResult
from ._modelo_work_wizard_payloads import WizardPromptedCasillaPayload, WorkWizardResult
from ._payloads_modelo_reconcile import (
    ModeloReconcileResult,
    ModeloReconciliationDiffPayload,
    WorkCompareTaxationResult,
)
from .modelo_aux_payloads import (
    EvidenceBundleCheckFindingPayload,
    EvidenceRecordRefPayload,
    ModeloAuditCheckResult,
    ModeloAuditExportResult,
    ModeloAuditViewResult,
    ModeloDescribeResult,
    ModeloListResult,
    ModeloRowPayload,
    WithholdingClaveBreakdownPayload,
    WorkflowRunPayload,
    WorkflowRunSummaryPayload,
    WorkHistoryResult,
    WorkRunDetailsResult,
    WorkRunResult,
    WorkRunsResult,
    WorkUnitHistoryEventPayload,
)

if TYPE_CHECKING:
    from ...application.modelo.export import ModeloExportResult as _AppModeloExportResult


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
    voluntary-filing close date and in-time / overdue posture. When overdue,
    it can carry an explicitly unassessed conditional Article 27 rate preview.
    It never asserts surcharge or interest liability. Distinct from the
    non-blocking advisory prose, which rides the envelope ``notices`` channel.
    """

    closes_on: date
    days_remaining: int | None = None
    days_overdue: int | None = None
    conditional_recargo_preview: WorkConditionalRecargoPreviewPayload | None = None

    @model_validator(mode="after")
    def _validate_deadline_posture(self) -> WorkDeadlinePosturePayload:
        """Reuse the application deadline state invariant at the JSON boundary."""
        validate_modelo_work_deadline_posture(
            closes_on=self.closes_on,
            days_remaining=self.days_remaining,
            days_overdue=self.days_overdue,
        )
        return self


class CalculationRevisionPayload(OutputSchema):
    """Shared JSON projection of a persisted :class:`CalculationRevision`.

    Built by
    :func:`calculation_revision_payload`.
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

FindingMessage = elided_prose(FINDING_MESSAGE_CAP)
"""A rendered finding message, elided at the cap rather than refused."""


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
    notes: FilingNotes | None = None
    aeat_accepted: bool = False
    status: ModeloRecordStatus
    superseded_at: datetime | None = None
    superseded_by_filing_record_id: FilingRecordId | None = None
    external_evidence: ExternalEvidencePayload | None = None
    amends_filing_record_id: FilingRecordId | None = None
    kind: Literal["internal_filing"] = "internal_filing"
    live_submission: bool = False

    @model_validator(mode="after")
    def _validate_filing_record_grounding(self) -> ModeloRecordPayload:
        """Keep the JSON projection aligned with the filing-record invariant."""
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


class FormulaPayload(OutputSchema):
    """One formula row in the formulas command output."""

    formula_id: FormulaId
    target_casilla_id: CasillaId
    input_casilla_ids: tuple[CasillaId, ...]
    input_bindings: tuple[BindingId, ...]
    input_parameters: tuple[ParameterId, ...]
    input_relations: tuple[RelationId, ...]
    expression: dict[str, object]
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]


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
    """Work-unit picker result returned by ``aeat app modelo work select``.

    Carries the same listing as :class:`WorkListResult` plus the work unit the
    operator chose in an interactive TUI session. ``selected_work_unit_id`` is
    ``None`` in every scripted (non-``--tui``) invocation and in an
    interactive session where the operator quit the picker without choosing.
    """

    operation: str = "modelo.work.select"
    bucket_id_filter: str | None = None
    include_discarded: bool
    work_unit_count: int
    work_units: list[WorkUnitPayload]
    selected_work_unit_id: str | None = None


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


class WorkCalculateResult(CalculationRevisionCommandProjectionFields):
    """Successful ``modelo work calculate`` result payload.

    The calculate CLI flattens the persisted
    :class:`CalculationRevision` fields from
    :class:`CalculationRevisionPayload`
    (carried by the compact revision-command projection base),
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
    :func:`verify_modelo_revision` and returns the
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

    model_config = ConfigDict(**{**OutputSchema.model_config, "hide_input_in_errors": True})
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
    amends_filing_record_id: FilingRecordId


class ModeloRecordListResult(OutputSchema):
    """Filing-record listing returned by ``aeat app modelo filing-record list``."""

    operation: str = "modelo.filing_record.list"
    bucket_id_filter: str | None = None
    modelo_filter: str | None = None
    include_superseded: bool
    record_count: int
    records: list[ModeloRecordPayload]


class ModeloRecordShowResult(ModeloRecordPayload):
    """Filing-record detail returned by ``aeat app modelo filing-record view``."""

    operation: str = "modelo.filing_record.show"


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
    completeness_status: VerificationCompletenessStatus
    granted_verificado_completo: bool
    resolved_casilla_ids: list[CasillaId]
    missing_required_casilla_ids: list[CasillaId]
    run_at: str
    verified_by: str
    findings: list[FindingPayload]


class FormulasResult(OutputSchema):
    operation: str = "modelo.formulas"
    code: str
    revision: str
    filing_year: int | None = None
    period: str | None = None
    formula_count: int
    rows: tuple[FormulaPayload, ...]


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

    The payload mirrors
    :class:`ModeloLocalObservationResult`:
    values are stored in the calculation-observation repository for prefill.
    ``official_evidence``, ``filing_record_created``, and ``aeat_accepted``
    are pinned ``False`` -- :func:`~application.modelo.record_operator_local_observation`
    never stamps a ``ModeloRecord`` or :class:`ExternalEvidence` for this
    action, so the envelope cannot be constructed to look like AEAT-backed
    evidence.
    """

    operation: str = "modelo.filing_record.observe_local"
    modelo: str
    filing_year: int
    period: Period
    revision_id: RevisionId
    observation_key: str
    source_kind: ObservationSourceKind
    casilla_values: dict[CasillaId, DecimalWireText]
    casilla_count: NonNegativeInt
    captured_at: datetime
    captured_by: NonEmptyStr
    official_evidence: Literal[False] = False
    filing_record_created: Literal[False] = False
    aeat_accepted: Literal[False] = False


class ModeloCasillaResult(OutputSchema):
    """Single-casilla semantic detail returned by ``aeat app modelo casilla``.

    Projects
    :class:`ModeloCasillaDetailReport`
    into the JSON envelope: an operator can look up one casilla's official
    label, legal / source grounding, input kind, and, when the casilla is
    computed, the resolved formula ``expression`` from the authoritative
    :class:`CasillaId` definition on the
    resolved registry snapshot, without running a calculation. ``legal_refs``
    and ``source_refs`` stay required so the grounding survives the boundary.
    """

    operation: str = "modelo.casilla"
    modelo: str
    revision: str
    filing_year: int | None = None
    period: str | None = None
    casilla_id: CasillaId
    number: str
    label: str
    help_text: str | None = None
    section: tuple[str, ...] = ()
    data_type: str
    input_kind: str
    required: bool
    legal_refs: LegalRefs
    source_refs: SourceRefs
    binding: BindingId | None = None
    formula_id: FormulaId | None = None
    formula_expression: dict[str, object] | None = None


class CasillaRowPayload(OutputSchema):
    """One casilla row in the casillas output."""

    casilla_id: CasillaId
    number: str
    input_kind: str
    required: bool
    label: str
    help_text: str | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs


class ModeloCasillasResult(OutputSchema):
    """Casillas listing result."""

    operation: str = "modelo.casillas"
    modelo: str
    revision: str
    casilla_count: int
    rows: list[CasillaRowPayload]


class DataInventoryCasillaPayload(OutputSchema):
    """One casilla entry on the ``modelo requires`` data-inventory checklist.

    Projects :class:`~application.modelo.DataInventoryCasilla`. ``binding_id``
    and ``binding_source`` are populated only for ``ledger_derivable`` and
    ``profile_derivable`` rows; required and optional manual entries carry no
    binding (they are hand-entered).

    The grounding invariant — ``legal_refs`` and ``source_refs`` non-empty —
    belongs to the canonical
    :class:`~application.modelo.DataInventoryCasilla`, which refuses to build an
    ungrounded entry, so every consumer of the checklist inherits it rather than
    only the JSON surface. This schema is the wire shape of an entry that
    already satisfies it.
    """

    casilla_id: CasillaId
    number: str
    label: str
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]
    binding_id: BindingId | None = None
    binding_source: str | None = None


class ModeloRequiresResult(OutputSchema):
    """Data-inventory checklist result returned by ``aeat app modelo requires``.

    Composes the registry snapshot for one ``(modelo, filing_year, period)``
    into the operator-facing "what data do I need" checklist: casillas the
    operator must hand-enter (``required_manual``), casillas they may
    optionally enter (``optional_manual``), casillas the ledger aggregation
    mesh populates once the relevant transactions are imported and classified
    (``ledger_derivable``), and casillas populated from the active taxpayer
    profile (``profile_derivable``). The two cross-filing channels remain
    distinct as ``previous_filing`` and ``relation_prefill``;
    ``live_observation`` carries bucket-local observation, register, and
    invoice-backed sources, while ``unbucketed_sources`` preserves any binding
    pair outside the explicit classifier for the envelope advisory.

    ``unresolved_profile_bindings`` names the
    profile-derivable bindings the active profile has not yet supplied a fact
    for (e.g. an unset home-office usage ratio) so the operator can fix the
    gap before calculating, and ``unresolved_profile_keys`` names the profile
    facts those bindings consume, which is what the operator actually has to
    supply. ``profile_checked`` is ``False`` when no active profile was
    available to check.
    """

    operation: str = "modelo.requires"
    modelo: str
    revision: str
    filing_year: int
    period: str
    required_manual: list[DataInventoryCasillaPayload]
    optional_manual: list[DataInventoryCasillaPayload]
    ledger_derivable: list[DataInventoryCasillaPayload]
    profile_derivable: list[DataInventoryCasillaPayload]
    previous_filing: list[DataInventoryCasillaPayload]
    relation_prefill: list[DataInventoryCasillaPayload]
    live_observation: list[DataInventoryCasillaPayload]
    unbucketed_sources: list[DataInventoryCasillaPayload]
    unresolved_profile_bindings: list[BindingId]
    unresolved_profile_keys: list[str]
    profile_checked: bool


# ---------------------------------------------------------------------------
# P16 – singleton verb schemas
# ---------------------------------------------------------------------------


class ModeloExportPayload(OutputSchema):
    """Modelo export result (path reference only — no raw bytes in envelope).

    Distinct from the application :class:`ModeloExportResult`:
    the backend result carries the write metadata plus an absolute ``Path`` and
    extra audit fields; this envelope projects the path-reference receipt
    (fichero-BOE bytes are never carried) using ``output_path`` (stringified),
    ``byte_size``, and ``file_sha256``. Derive instances via :meth:`from_result`.
    """

    operation: str = "modelo.export"
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    bucket_id: BucketId
    modelo: str
    filing_year: int
    period: Period
    output_path: str
    byte_size: int
    file_sha256: str
    format: str
    bucket_event_id: str
    resolved_result_disposition: ResultDisposition
    payment_election: PaymentElection | None = None
    refund_election: RefundElection | None = None
    prior_domiciliation_election: PriorDomiciliationElectionProjection

    @classmethod
    def from_result(cls, result: _AppModeloExportResult) -> ModeloExportPayload:
        """Project the application :class:`ModeloExportResult` into this CLI :class:`ModeloExportPayload` envelope.

        ``output_path`` is stringified from the application ``Path``; the
        fichero-BOE bytes are intentionally excluded (the file is written to
        ``output_path``). ``operation`` is the CLI-only discriminator left at its
        default; the backend's ``exported_at``/``actor`` audit fields are not
        surfaced in the JSON envelope.
        """
        return cls(
            work_unit_id=result.work_unit_id,
            calculation_revision_id=result.calculation_revision_id,
            bucket_id=result.bucket_id,
            modelo=result.modelo,
            filing_year=result.filing_year,
            period=result.period,
            output_path=str(result.output_path),
            byte_size=result.byte_size,
            file_sha256=result.file_sha256,
            format=result.format,
            bucket_event_id=result.bucket_event_id,
            resolved_result_disposition=result.resolved_result_disposition,
            payment_election=result.payment_election,
            refund_election=result.refund_election,
            prior_domiciliation_election=result.prior_domiciliation_election,
        )


class DeltaRowPayload(OutputSchema):
    """One grounded :class:`CasillaId` comparison row in ``modelo.compare``.

    Preserves formula, legal-reference, and source-reference identifiers so the
    :class:`ModeloCompareResult` envelope does not lose registry provenance.
    """

    casilla_id: CasillaId
    label: str
    section: str
    year_a_value: str
    year_b_value: str
    delta: str
    pct_change: str | None
    formula_id: FormulaId | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs


class CompareSectionPayload(OutputSchema):
    """Named section grouping for :class:`DeltaRowPayload` rows."""

    section: str
    rows: list[DeltaRowPayload]


class ModeloCompareResult(OutputSchema):
    """Envelope result for ``modelo.compare``.

    Rows are carried both sectioned and flattened so table rendering and JSON
    consumers share the same :class:`DeltaRowPayload` provenance fields.
    """

    operation: str = "modelo.compare"
    modelo: str
    year_a: int
    year_b: int
    year_a_revision_id: RevisionId
    year_b_revision_id: RevisionId
    year_a_is_draft: bool
    year_b_is_draft: bool
    sections: list[CompareSectionPayload]
    delta_rows: list[DeltaRowPayload]


class ModeloLifecycleEventPayload(OutputSchema):
    """One bucket event in the modelo history output.

    Projects :class:`~cadrumo.domain.buckets.BucketEvent` through the identity
    aliases and closed enums that package already exports, rather than
    re-declaring their shape as free strings. Enum members and ``datetime``
    values render to the same JSON the former hand-built mapping emitted, so the
    wire form is unchanged.
    """

    event_id: BucketEventId
    event_type: BucketEventType
    occurred_at: datetime
    actor: BucketActorLabel
    object_type: BucketEventObjectType
    object_id: BucketObjectId
    payload: dict[str, str]


class ModeloHistoryResult(OutputSchema):
    """Chronological modelo lifecycle history result.

    ``period`` stays a free token: the filter accepts registry period codes and
    the censo lifecycle words (``alta`` / ``modificacion`` / ``baja``), and an
    unmatched token legitimately yields an empty history rather than a refusal.
    Only its blankness is constrained.
    """

    operation: str = "modelo.history"
    modelo: NonEmptyStr
    year: FilingYear | None = None
    period: NonEmptyStr | None = None
    count: NonNegativeInt
    events: list[ModeloLifecycleEventPayload]


class CasillaObservationPayload(OutputSchema):
    """One typed :class:`CasillaId` observation for projection-style results.

    Used by :class:`ModeloProjectResult` and
    :class:`WorkPreviewMaritimeExemptionResult`; ``legal_refs`` and
    ``source_refs`` stay required to preserve calculation grounding in CLI JSON.
    """

    casilla_id: CasillaId
    value: str
    formula_id: FormulaId | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs


class M130AccumulatedPayload(OutputSchema):
    """M130 summary inputs that feed :class:`ModeloProjectResult`.

    These stringified Decimal fields are operator-facing totals; the grounded
    per-casilla path is :class:`CasillaObservationPayload`.
    """

    ingresos: DecimalWireText
    gastos: DecimalWireText
    rendimiento_neto: DecimalWireText
    pagos_fraccionados: DecimalWireText


class M100ProjectionPayload(OutputSchema):
    """Projected M100 summary values in :class:`ModeloProjectResult`.

    This flat view gives stable top-line JSON keys; formula provenance lives in
    ``ModeloProjectResult.casilla_observations``.
    """

    base_liquidable_general_0505: str
    pagos_fraccionados_0604: str
    cuota_integra_estatal_0545: str
    cuota_integra_autonomica_0546: str
    cuota_liquida_estatal_0595: str
    cuota_liquida_autonomica_0596: str
    cuota_resultante_0597: str


class ModeloProjectResult(OutputSchema):
    """Envelope result for ``modelo.project``.

    Combines :class:`M130AccumulatedPayload` source totals, the flat
    :class:`M100ProjectionPayload` summary, and the required
    :class:`CasillaObservationPayload` provenance list.
    """

    operation: str = "modelo.project"
    year: int
    ccaa: str
    quarters_filed: int
    quarters_available: list[str]
    is_extrapolated: bool
    m130_accumulated: M130AccumulatedPayload
    casilla_observations: list[CasillaObservationPayload]
    m100_projection: M100ProjectionPayload


class ModeloReadinessMissingRequirementPayload(OutputSchema):
    """One missing profile requirement in the readiness result."""

    section_key: str
    field_key: str
    selector: str
    label: str
    legal_refs: list[str]
    modelos: list[str]


class ModeloReadinessMissingBindingPayload(OutputSchema):
    """One calculation binding readiness cannot satisfy."""

    binding_id: str
    source: BindingSourceKind
    input_channel: str


class LedgerIssuePayload(OutputSchema):
    """One ledger issue in the readiness result."""

    transaction_id: TransactionId
    reason: str
    detail: IssueDetail


class ModeloReadinessResult(OutputSchema):
    """Active-profile modelo readiness report."""

    operation: str = "modelo.readiness"
    profile_id: ProfileId
    modelo: str
    revision_id: RevisionId
    filing_year: int
    period: Period
    ready: bool
    profile_ready: bool
    profile_refusal: str
    registry_ready: bool
    registry_refusal: str
    binding_ready: bool
    missing: list[ModeloReadinessMissingRequirementPayload]
    missing_bindings: list[ModeloReadinessMissingBindingPayload]
    ledger_preflight_required: bool
    ledger_ready: bool | None
    ledger_period: Period | None
    ledger_checked_transaction_count: int
    ledger_issues: list[LedgerIssuePayload]


class WorkResumeResult(OutputSchema):
    """Workflow resume precondition and context result.

    Combines the resumable
    :class:`WorkflowResumeContext` with selector
    metadata from
    :class:`WorkflowResumeTargetResolution`. The
    ``obligation`` payload is the serialized
    :class:`ModeloDeadline` the workflow engine would use
    for a fresh attempt.
    """

    operation: str = "modelo.work.resume"
    prior_workflow_run_id: str
    resolved_source: str | None = None
    work_unit_id: WorkUnitId | None = None
    short_work_unit_id: str | None = None
    calculation_revision_id: CalculationRevisionId | None = None
    short_calculation_revision_id: str | None = None
    modelo: str
    period: Period
    aborted_reason: str
    obligation: dict[str, object]


class ModeloAggregateResult(OutputSchema):
    """Per-modelo aggregation result, projected from the canonical service result.

    Every field is typed from the contract
    :class:`~application.aggregation.PerModeloAggregationResult` already
    enforces: a bounded non-blank modelo, the closed
    :class:`~application.aggregation.PerModeloAggregationContributor` provider,
    closed :class:`~core.BindingSourceKind` source kinds, and non-negative
    counters. Redeclaring them as bare strings and unbounded integers made this
    transport shell strictly more permissive than the result it renders, so an
    empty modelo, an unknown provider, a bogus source kind, or a negative count
    could be emitted as a valid envelope. Build it through
    :meth:`from_aggregation_result` rather than field-by-field.

    ``clave_breakdown`` carries the Modelo 190 per-clave retención rows (empty
    for every other modelo); it is primary structured result data the command
    produces, sourced from the already-ingested per-perceptor-clave withholding
    detail, not an incidental diagnostic.

    ``clave_breakdown`` and ``observation_count`` are deliberately NOT
    cross-validated against each other. They are different slices of the same
    ledger, not one derived from the other: ``observation_count`` reflects the
    retenciones provider's own aggregation (``result.log_fields``), while
    ``clave_breakdown`` is a separate CLI-local projection of the withholding
    observations the ``--withholding-observation`` flags supplied directly
    (see ``aggregate_withholding_by_clave`` in ``_modelo_aggregate_cli.py``). A
    prior invariant asserting ``breakdown_percepciones <= observation_count``
    was removed: it was never true by construction (the two counts have no
    routed relationship for M190, the only modelo that ever populates
    ``clave_breakdown``) and it rejected every M190 call whose withholding
    observations were not additionally routed through the retenciones
    provider's own store.
    """

    operation: str = "modelo.aggregate"
    modelo: ModeloCode
    period: Period
    provider: PerModeloAggregationContributor
    observation_count: NonNegativeInt
    source_kinds: list[BindingSourceKind] = Field(default_factory=list)
    result_row_count: NonNegativeInt
    clave_breakdown: list[WithholdingClaveBreakdownPayload] = Field(default_factory=list)

    @field_validator("provider", mode="before")
    @classmethod
    def _coerce_provider(cls, value: object) -> object:
        """Hydrate a raw provider token to its closed-enum member.

        The strict schema base does not coerce ``str`` -> ``StrEnum``, so a
        payload re-validated from its own JSON rendering is lifted here. An
        unknown token raises rather than passing through as free text.
        """
        if isinstance(value, str) and not isinstance(value, PerModeloAggregationContributor):
            return PerModeloAggregationContributor(value)
        return value

    @field_validator("source_kinds", mode="before")
    @classmethod
    def _coerce_source_kinds(cls, value: object) -> object:
        """Hydrate raw source-kind tokens to their closed-enum members."""
        if isinstance(value, list):
            return [
                BindingSourceKind(item) if isinstance(item, str) and not isinstance(item, BindingSourceKind) else item
                for item in value
            ]
        return value

    @field_validator("source_kinds")
    @classmethod
    def _source_kinds_are_unique(cls, value: list[BindingSourceKind]) -> list[BindingSourceKind]:
        """Mirror the canonical result's uniqueness invariant."""
        if len(value) != len(set(value)):
            raise ValueError("source_kinds must be unique")
        return value

    @classmethod
    def from_aggregation_result(
        cls,
        result: PerModeloAggregationResult,
        *,
        clave_breakdown: Sequence[WithholdingClaveBreakdown] = (),
    ) -> ModeloAggregateResult:
        """Project the canonical service result onto the CLI transport shape.

        The one construction path, so the envelope cannot carry a modelo,
        period, provider, source-kind set, or counter the service did not
        produce. Counters come from the result's own
        :class:`~application.aggregation.PerModeloAggregationLogFields`, which
        already bounds them.

        Args:
            result: The canonical per-modelo aggregation result.
            clave_breakdown: Modelo 190 per-clave rows, empty elsewhere.
        """
        return cls(
            modelo=result.modelo,
            period=result.period,
            provider=result.provider,
            observation_count=result.log_fields.observation_count,
            source_kinds=list(result.source_kinds),
            result_row_count=result.log_fields.result_row_count,
            clave_breakdown=[
                WithholdingClaveBreakdownPayload(
                    clave=row.clave,
                    percepcion_count=row.percepcion_count,
                    percibido_total=str(row.percibido_total),
                    retencion_total=str(row.retencion_total),
                )
                for row in clave_breakdown
            ],
        )


class WorkPreviewMaritimeExemptionResult(OutputSchema):
    """Envelope result for ``modelo.work.preview_maritime_exemption``.

    ``casilla_values`` is a convenience mapping keyed by :class:`CasillaId`;
    ``observations`` reuses :class:`CasillaObservationPayload` for grounded
    legal-reference and source-reference identifiers.
    """

    operation: str = "modelo.work.preview_maritime_exemption"
    worker_class: str | None = None
    vessel_flag: str | None = None
    waters_type: str | None = None
    vessel_registry: str | None = None
    retmar_registered: bool = False
    retmar_mandatory_filing: bool = False
    retmar_warning: str | None = None
    casilla_values: dict[CasillaId, str] = Field(default_factory=dict)
    observations: list[CasillaObservationPayload] = Field(default_factory=list)


__all__ = [
    "BindingEncodedOptionPayload",
    "BindingListRowPayload",
    "BindingPreviewRowPayload",
    "CalculationRevisionPayload",
    "CalculationRevisionSummaryPayload",
    "CasillaObservationPayload",
    "CasillaRowPayload",
    "CompareSectionPayload",
    "CrossPeriodCleanStatePayload",
    "CrossPeriodDependencyEvidencePayload",
    "CrossPeriodDependencyInventoryItemPayload",
    "CrossPeriodDependencyRequirementPayload",
    "DataInventoryCasillaPayload",
    "DeltaRowPayload",
    "EvidenceBundleCheckFindingPayload",
    "EvidenceRecordRefPayload",
    "FilingRecordImportResult",
    "FilingRecordLocalObservationResult",
    "FindingPayload",
    "FormulaPayload",
    "FormulasResult",
    "IvaWalletBalanceResult",
    "IvaWalletOverrideResult",
    "IvaWalletSeedResult",
    "LedgerIssuePayload",
    "M100ProjectionPayload",
    "M130AccumulatedPayload",
    "ModeloAggregateResult",
    "ModeloAuditCheckResult",
    "ModeloAuditExportResult",
    "ModeloAuditViewResult",
    "ModeloBindingsListResult",
    "ModeloBindingsPreviewResult",
    "ModeloCasillaResult",
    "ModeloCasillasResult",
    "ModeloCompareResult",
    "ModeloDescribeResult",
    "ModeloExportPayload",
    "ModeloHistoryResult",
    "ModeloLifecycleEventPayload",
    "ModeloListResult",
    "ModeloPortalCompatibilityRefPayload",
    "ModeloProjectResult",
    "ModeloReadinessMissingBindingPayload",
    "ModeloReadinessMissingRequirementPayload",
    "ModeloReadinessResult",
    "ModeloReconcileResult",
    "ModeloReconciliationDiffPayload",
    "ModeloRecordListResult",
    "ModeloRecordPayload",
    "ModeloRecordShowResult",
    "ModeloRenamePayload",
    "ModeloRequiresResult",
    "ModeloRowPayload",
    "ModeloSupportMatrixEntryPayload",
    "ModeloSupportMatrixResult",
    "ObservationPayload",
    "ResultSummaryRowPayload",
    "SourceProvenancePayload",
    "VerificationReportListResult",
    "VerificationReportPayload",
    "VerificationReportShowResult",
    "WithholdingClaveBreakdownPayload",
    "WizardPromptedCasillaPayload",
    "WorkAmendResult",
    "WorkCalculateResult",
    "WorkCompareTaxationResult",
    "WorkCreateResult",
    "WorkDependenciesResult",
    "WorkDiscardResult",
    "WorkFileResult",
    "WorkHistoryResult",
    "WorkListResult",
    "WorkObservationsResult",
    "WorkPreviewMaritimeExemptionResult",
    "WorkRenameResult",
    "WorkResumeResult",
    "WorkReviewPayload",
    "WorkReviewResult",
    "WorkRevisionResult",
    "WorkRevisionsResult",
    "WorkRunDetailsResult",
    "WorkRunResult",
    "WorkRunsResult",
    "WorkStatusResult",
    "WorkUnitHistoryEventPayload",
    "WorkUnitPayload",
    "WorkVerifyResult",
    "WorkWizardResult",
    "WorkflowRunPayload",
    "WorkflowRunSummaryPayload",
]
