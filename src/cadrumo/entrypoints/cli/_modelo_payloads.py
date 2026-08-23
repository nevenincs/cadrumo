"""Typed ``--json`` payload schemas for modelo command envelopes.

Each command result is a strict
:class:`OutputSchema` subclass registered by
CommandSpec schema authority for a stable command path
and wrapped at emit time in
:class:`SchemaEnvelope` through
:func:`_emit_envelope`. This file is the CLI-side
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

from pydantic import Field, field_validator, model_validator

from ...application.aggregation import (
    PerModeloAggregationContributor,
    PerModeloAggregationResult,
)
from ...application.calculations import ObservationSourceKind, PriorDomiciliationElectionProjection
from ...application.modelo import ModeloWorkReview, validate_modelo_work_deadline_posture
from ...core import (
    BindingSourceKind,
    CasillaId,
    OperatorActionAxis,
    PaymentElection,
    Period,
    RefundElection,
    ResultDisposition,
)
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
from ...domain.buckets import (
    BucketActorLabel,
    BucketEventId,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.calculations.registry import (
    BindingId,
    FormulaId,
    LegalRefId,
    ParameterId,
    RelationId,
    RevisionId,
    SourceRefId,
    VerificationExpectationId,
    WithholdingClaveBreakdown,
)
from ...domain.modelos import (
    ExternalEvidenceKind,
    M303RectificativaMotive,
    ModeloCode,
    ModeloRecordStatus,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ._decimal_wire import DecimalWireText
from ._modelo_aux_payloads import (
    EvidenceBundleCheckFindingPayload,
    EvidenceRecordRefPayload,
    ModeloAuditCheckResult,
    ModeloAuditExportResult,
    ModeloAuditShowResult,
    ModeloDescribeResult,
    ModeloListResult,
    ModeloRowPayload,
    WithholdingClaveBreakdownPayload,
    WorkflowRunPayload,
    WorkHistoryResult,
    WorkRunsResult,
    WorkUnitHistoryEventPayload,
)
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
    CalculationRevisionProjectionFields,
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

if TYPE_CHECKING:
    from ...application.modelo import ModeloExportResult as _AppModeloExportResult


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
    message: str = Field(min_length=1, max_length=500)
    action: ResolvedPreconditionAction | None = None
    legal_refs: list[LegalRefId] = Field(min_length=1)
    source_refs: list[SourceRefId] = Field(default_factory=list)


class CrossPeriodDependencyRequirementPayload(OutputSchema):
    """One upstream filing dependency declared by the registry."""

    source_modelo: str
    filing_year: int
    period: Period
    source_casilla_ids: tuple[CasillaId, ...]
    origin: str
    origin_ids: tuple[str, ...]
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
    """

    verification_report_id: VerificationReportId
    calculation_revision_id: CalculationRevisionId
    completeness_status: str
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
    reference_id: str = Field(min_length=1, max_length=128)
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
    filing_year: int = Field(ge=2000, le=2099)
    period: Period
    filed_at: datetime
    filed_by: str = Field(min_length=1, max_length=500)
    notes: str | None = Field(default=None, min_length=1, max_length=500)
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
    (carried by the shared :class:`CalculationRevisionProjectionFields` base),
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


class WorkRevisionsResult(OutputSchema):
    """Calculation-revision listing returned by ``aeat app modelo work revisions``.

    Each entry in ``revisions`` is a
    :class:`CalculationRevisionPayload`
    carrying the full casilla table, typed observations, and provenance for one
    persisted :class:`CalculationRevision`.
    """

    operation: str = "modelo.work.revisions"
    work_unit_id_filter: str | None = None
    revision_count: int
    revisions: list[CalculationRevisionPayload]


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
    completeness_status: str
    granted_verificado_completo: bool
    resolved_casilla_ids: list[CasillaId]
    missing_required_casilla_ids: list[CasillaId]
    run_at: str
    verified_by: str
    findings: list[FindingPayload]


class WorkReviewResult(OutputSchema):
    """Envelope payload carrying the canonical application review record.

    The CLI boundary wraps :class:`ModeloWorkReview` unchanged. Schema,
    origins, realised values, progress, findings, and blocker references remain
    owned by ``application.modelo`` rather than being redeclared here.
    """

    operation: Literal["modelo.work.review"] = "modelo.work.review"
    review: ModeloWorkReview


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
    completeness_status: str
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
    evidence_kind: ExternalEvidenceKind
    evidence_reference_id: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _validate_imported_evidence_matches_record(self) -> FilingRecordImportResult:
        """Prevent import metadata from diverging from the attested evidence row."""
        if self.external_evidence is None:
            raise ValueError("imported filing record must carry external evidence")
        if self.external_evidence.kind is not self.evidence_kind:
            raise ValueError("evidence_kind must match external evidence")
        if self.external_evidence.reference_id != self.evidence_reference_id:
            raise ValueError("evidence_reference_id must match external evidence")
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
    casilla_count: int = Field(ge=0)
    captured_at: datetime
    captured_by: str = Field(min_length=1)
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
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
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
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


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
    """

    casilla_id: CasillaId
    number: str
    label: str
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
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
    legal_refs: list[LegalRefId] = Field(min_length=1)
    source_refs: list[SourceRefId] = Field(min_length=1)


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
    object_id: str = Field(min_length=1, max_length=128)
    payload: dict[str, str]


class ModeloHistoryResult(OutputSchema):
    """Chronological modelo lifecycle history result.

    ``period`` stays a free token: the filter accepts registry period codes and
    the censo lifecycle words (``alta`` / ``modificacion`` / ``baja``), and an
    unmatched token legitimately yields an empty history rather than a refusal.
    Only its blankness is constrained.
    """

    operation: str = "modelo.history"
    modelo: str = Field(min_length=1)
    year: int | None = Field(default=None, ge=2000, le=2099)
    period: str | None = Field(default=None, min_length=1)
    count: int = Field(ge=0)
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
    legal_refs: list[LegalRefId] = Field(min_length=1)
    source_refs: list[SourceRefId] = Field(min_length=1)


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
    operator_action: OperatorActionAxis


class ModeloReadinessMissingBindingPayload(OutputSchema):
    """One calculation binding readiness cannot satisfy."""

    binding_id: str
    source: BindingSourceKind
    input_channel: str
    operator_action: OperatorActionAxis


class LedgerIssuePayload(OutputSchema):
    """One ledger issue in the readiness result."""

    transaction_id: TransactionId
    reason: str
    detail: str = Field(min_length=1, max_length=512)
    operator_action: OperatorActionAxis


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
    modelo: str = Field(min_length=1, max_length=16)
    period: Period
    provider: PerModeloAggregationContributor
    observation_count: int = Field(ge=0)
    source_kinds: list[BindingSourceKind] = Field(default_factory=list)
    result_row_count: int = Field(ge=0)
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
    "ModeloAuditShowResult",
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
    "WorkReviewResult",
    "WorkRevisionResult",
    "WorkRevisionsResult",
    "WorkRunsResult",
    "WorkStatusResult",
    "WorkUnitHistoryEventPayload",
    "WorkUnitPayload",
    "WorkVerifyResult",
    "WorkWizardResult",
    "WorkflowRunPayload",
]
