"""Typed ``--json`` payload schemas for modelo command envelopes.

Each payload here is a :class:`OutputSchema` subclass registered for its
command envelope.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field, model_validator

from ...core import Period
from ...core.identity import BucketId
from ...domain.calculations.registry import (
    BindingId,
    CasillaId,
    FormulaId,
    LegalRefId,
    ParameterId,
    RelationId,
    RevisionId,
    SourceRefId,
)
from ...domain.modelos._ids import (
    CalculationRevisionId,
    FilingRecordId,
    VerificationReportId,
    WorkUnitId,
)
from ._payloads_modelo_reconcile import (
    ModeloReconcileResult,
    ModeloReconciliationDiffPayload,
    WorkCompareTaxationResult,
)
from ._schemas import OutputSchema, register_schema

if TYPE_CHECKING:
    from ...application.modelo import ModeloExportResult as _AppModeloExportResult


class WorkUnitPayload(OutputSchema):
    """Work unit fields shared across create / status / rename / discard."""

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


class ObservationPayload(OutputSchema):
    """One typed casilla observation with full provenance."""

    casilla_id: CasillaId
    value: str  # serialised Decimal
    formula_id: FormulaId | None = None
    operand_refs: tuple[str, ...] = ()
    operand_casilla_refs: tuple[CasillaId, ...] = ()
    operand_values: tuple[str, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _operand_casilla_refs_are_traced(self) -> ObservationPayload:
        missing = tuple(ref for ref in self.operand_casilla_refs if ref not in self.operand_refs)
        if missing:
            raise ValueError(
                f"observation payload for {self.casilla_id!r} declares operand_casilla_refs "
                f"that are absent from operand_refs: {missing!r}",
            )
        return self


class WorkRecargoPayload(OutputSchema):
    """Recargo band provenance for an overdue work-unit filing deadline.

    Surfaces the Art. 27 LGT surcharge band the engine resolved for a
    late filing so a JSON consumer reads the same band id, percentage,
    interest applicability, and binding legal reference the text-mode
    plazo lines render.
    """

    band_id: str
    surcharge_pct: str  # serialised Decimal
    interest_applies: bool
    legal_ref: str


class WorkPlazoDeadlinePayload(OutputSchema):
    """Filing-deadline (plazo voluntario) state for the work unit.

    Structured result data the calculate verb exists to surface: the
    voluntary-filing close date, the in-time / overdue posture, and — when
    overdue — the resolved Art. 27 LGT recargo band. Distinct from the
    non-blocking advisory prose, which rides the envelope ``notices``
    channel.
    """

    closes_on: str  # ISO date
    days_remaining: int | None = None
    days_overdue: int | None = None
    recargo: WorkRecargoPayload | None = None


class ResultSummaryRowPayload(OutputSchema):
    """One headline-result summary row (registry-declared lead figure)."""

    role: str
    casilla_id: CasillaId
    value: str  # serialised Decimal
    label: str


class CalculationRevisionPayload(OutputSchema):
    """Calculation revision fields surfaced by calculate / revisions commands."""

    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    state: str
    casilla_values: dict[CasillaId, str]  # casilla_id -> str(Decimal)
    observations: tuple[ObservationPayload, ...]
    result_summary: tuple[ResultSummaryRowPayload, ...] = ()
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
    """One verification finding row."""

    kind: str
    severity: str
    casilla_id: CasillaId | None = None
    expectation_id: str | None = None
    message: str
    next_action: str | None = None
    legal_refs: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


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
    target_revision_id: str
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
    filing_record_id: str | None = None
    calculation_revision_id: str | None = None
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
    """Verification report fields returned by verify / verification-report commands."""

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
    """External-evidence reference embedded in a filing record."""

    kind: str
    reference_id: str
    imported_at: str


class ModeloRecordPayload(OutputSchema):
    """Filing record fields returned by file / filing-record commands."""

    filing_record_id: FilingRecordId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    bucket_id: BucketId
    modelo: str
    filing_year: int
    period: Period
    filed_at: str
    filed_by: str
    notes: str | None = None
    aeat_accepted: bool | None = None
    status: str
    superseded_at: str | None = None
    superseded_by_filing_record_id: FilingRecordId | None = None
    external_evidence: ExternalEvidencePayload | None = None
    amends_filing_record_id: FilingRecordId | None = None
    kind: str = "internal_filing"
    live_submission: bool = False


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


@register_schema("modelo.work.create")
class WorkCreateResult(OutputSchema):
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


@register_schema("modelo.work.list")
class WorkListResult(OutputSchema):
    """Work-unit listing result returned by ``aeat app modelo work list``."""

    operation: str = "modelo.work.list"
    bucket_id_filter: str | None = None
    include_discarded: bool
    work_unit_count: int
    work_units: list[WorkUnitPayload]


@register_schema("modelo.work.status")
class WorkStatusResult(OutputSchema):
    """Work-unit status result returned by ``aeat app modelo work status``."""

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


@register_schema("modelo.work.rename")
class WorkRenameResult(OutputSchema):
    """Work-unit rename confirmation returned by ``aeat app modelo work rename``."""

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


@register_schema("modelo.work.discard")
class WorkDiscardResult(OutputSchema):
    """Work-unit discard confirmation returned by ``aeat app modelo work discard``.

    The discard is an audit-grade state transition: the work unit is
    preserved with ``discarded_at`` / ``discarded_by`` / ``discard_reason``
    populated and subsequent mutations are rejected.
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


@register_schema("modelo.work.calculate")
class WorkCalculateResult(OutputSchema):
    operation: str = "modelo.work.calculate"
    saved: bool = True
    saved_confirmation: str
    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    state: str
    casilla_values: dict[CasillaId, str]
    observations: tuple[ObservationPayload, ...]
    result_summary: tuple[ResultSummaryRowPayload, ...] = ()
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
    modality: str | None = None
    modality_reason: str | None = None
    authorization_state: str | None = None
    deadline: WorkPlazoDeadlinePayload | None = None


@register_schema("modelo.work.revisions")
class WorkRevisionsResult(OutputSchema):
    """Calculation-revision listing returned by ``aeat app modelo work revisions``.

    Each entry in ``revisions`` is a :class:`CalculationRevisionPayload`
    carrying the full casilla table, typed observations, and provenance.
    """

    operation: str = "modelo.work.revisions"
    work_unit_id_filter: str | None = None
    revision_count: int
    revisions: list[CalculationRevisionPayload]


@register_schema("modelo.work.revision")
class WorkRevisionResult(OutputSchema):
    """Single-revision shape returned by ``aeat app modelo work revision``.

    Carries the same calculation-revision fields as
    :class:`WorkCalculateResult` minus the persistence-confirmation
    pair (``saved`` / ``saved_confirmation``). Modelo 202 modality
    surfaces on the same optional fields so the inspection verb stays
    contract-compatible with the calculate verb's output.
    """

    operation: str = "modelo.work.revision"
    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    state: str
    casilla_values: dict[CasillaId, str]
    observations: tuple[ObservationPayload, ...]
    result_summary: tuple[ResultSummaryRowPayload, ...] = ()
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
    modality: str | None = None
    modality_reason: str | None = None


@register_schema("modelo.work.verify")
class WorkVerifyResult(OutputSchema):
    """Verification report returned by ``aeat app modelo work verify``.

    On a successful verificado-completo verdict the revision transitions to
    ``verificado_completo``; on a refused verdict the revision is unchanged
    and ``findings`` names every blocking or advisory issue.
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


@register_schema("modelo.work.dependencies")
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


@register_schema("modelo.work.file")
class WorkFileResult(OutputSchema):
    """Internal-filing confirmation returned by ``aeat app modelo work file``.

    Records that the revision was marked as internally filed. Does NOT
    represent an AEAT submission; ``live_submission`` is always ``False``.
    """

    operation: str = "modelo.work.file"
    filing_record_id: FilingRecordId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    bucket_id: BucketId
    modelo: str
    filing_year: int
    period: Period
    filed_at: str
    filed_by: str
    notes: str | None = None
    aeat_accepted: bool | None = None
    status: str
    superseded_at: str | None = None
    superseded_by_filing_record_id: FilingRecordId | None = None
    external_evidence: ExternalEvidencePayload | None = None
    amends_filing_record_id: FilingRecordId | None = None
    kind: str = "internal_filing"
    live_submission: bool = False


@register_schema("modelo.work.amend")
class WorkAmendResult(OutputSchema):
    """Amendment filing confirmation returned by ``aeat app modelo work amend``.

    Carries the amendment-specific pair (``amendment_kind``,
    ``amends_filing_record_id``) above the standard filing-record body.
    ``live_submission`` is always ``False``; does NOT submit to AEAT.
    """

    operation: str = "modelo.work.amend"
    amendment_kind: str
    amends_filing_record_id: FilingRecordId
    filing_record_id: FilingRecordId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    bucket_id: BucketId
    modelo: str
    filing_year: int
    period: Period
    filed_at: str
    filed_by: str
    notes: str | None = None
    aeat_accepted: bool | None = None
    status: str
    superseded_at: str | None = None
    superseded_by_filing_record_id: FilingRecordId | None = None
    external_evidence: ExternalEvidencePayload | None = None
    kind: str = "internal_filing"
    live_submission: bool = False


@register_schema("modelo.filing_record.list")
class ModeloRecordListResult(OutputSchema):
    """Filing-record listing returned by ``aeat app modelo filing-record list``."""

    operation: str = "modelo.filing_record.list"
    bucket_id_filter: str | None = None
    modelo_filter: str | None = None
    include_superseded: bool
    record_count: int
    records: list[ModeloRecordPayload]


@register_schema("modelo.filing_record.view")
class ModeloRecordShowResult(OutputSchema):
    """Filing-record detail returned by ``aeat app modelo filing-record view``."""

    operation: str = "modelo.filing_record.show"
    filing_record_id: FilingRecordId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    bucket_id: BucketId
    modelo: str
    filing_year: int
    period: Period
    filed_at: str
    filed_by: str
    notes: str | None = None
    aeat_accepted: bool | None = None
    status: str
    superseded_at: str | None = None
    superseded_by_filing_record_id: FilingRecordId | None = None
    external_evidence: ExternalEvidencePayload | None = None
    amends_filing_record_id: FilingRecordId | None = None
    kind: str = "internal_filing"
    live_submission: bool = False


@register_schema("modelo.verification_report.list")
class VerificationReportListResult(OutputSchema):
    """Verification-report listing returned by ``aeat app modelo verification-report list``."""

    operation: str = "modelo.verification_report.list"
    calculation_revision_id_filter: str | None = None
    report_count: int
    reports: list[VerificationReportPayload]


@register_schema("modelo.verification_report.view")
class VerificationReportShowResult(OutputSchema):
    """Verification-report detail returned by ``aeat app modelo verification-report view``."""

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


@register_schema("modelo.formulas")
class FormulasResult(OutputSchema):
    operation: str = "modelo.formulas"
    code: str
    revision: str
    filing_year: int | None = None
    period: str | None = None
    formula_count: int
    rows: tuple[FormulaPayload, ...]


class EvidenceRecordRefPayload(OutputSchema):
    """One record reference entry inside an evidence bundle manifest."""

    object_type: str
    object_id: str
    content_sha256: str
    payload_size_bytes: int


class EvidenceBundleCheckFindingPayload(OutputSchema):
    """One check outcome from a bundle verification pass."""

    check: str
    passed: bool
    detail: str = ""


@register_schema("modelo.audit.show")
class ModeloAuditShowResult(OutputSchema):
    """Evidence bundle manifest render result (audit show)."""

    operation: str = "modelo.audit.show"
    bundle_id: str
    manifest_version: int
    bucket_id: str
    work_unit_id: str
    calculation_revision_id: str | None = None
    filing_record_id: str | None = None
    verification_state: str
    completeness_ratio: float
    records: list[EvidenceRecordRefPayload]
    created_at: str
    notes: str = ""


@register_schema("modelo.audit.check")
class ModeloAuditCheckResult(OutputSchema):
    """Evidence bundle integrity re-verification result (audit check)."""

    operation: str = "modelo.audit.check"
    bundle_id: str
    verification_state: str
    completeness_ratio: float
    findings: list[EvidenceBundleCheckFindingPayload]


@register_schema("modelo.audit.export")
class ModeloAuditExportResult(OutputSchema):
    """Evidence bundle ZIP export result (audit export).

    Uses output path reference + record count instead of raw bytes so
    the JSON envelope never persists binary content.
    """

    operation: str = "modelo.audit.export"
    bucket_id: str
    bundle_id: str
    output: str
    verification_state: str
    records: int


@register_schema("modelo.audit.replay")
class ModeloAuditReplayResult(OutputSchema):
    """Evidence bundle replay result (audit replay)."""

    operation: str = "modelo.audit.replay"
    bundle_id: str
    verification_state: str
    completeness_ratio: float
    findings: list[EvidenceBundleCheckFindingPayload]


class WorkUnitHistoryEventPayload(OutputSchema):
    """One event row in a work-unit history stream."""

    event_id: str
    occurred_at: str
    event_type: str
    object_type: str
    object_id: str
    actor: str
    payload: dict[str, str]


@register_schema("modelo.work.history")
class WorkHistoryResult(OutputSchema):
    """Work-unit event history result."""

    operation: str = "modelo.work.history"
    bucket_id: str
    work_unit_id: str
    event_count: int
    events: list[WorkUnitHistoryEventPayload]


class WorkflowRunPayload(OutputSchema):
    """One workflow run row in the runs listing."""

    run_id: str
    modelo: str | None
    period: str | None
    final_stage: str
    aborted_reason: str | None
    started_at: str


@register_schema("modelo.work.runs")
class WorkRunsResult(OutputSchema):
    """Workflow runs listing result."""

    operation: str = "modelo.work.runs"
    run_count: int
    runs: list[WorkflowRunPayload]


@register_schema("modelo.filing_record.import")
class FilingRecordImportResult(OutputSchema):
    """Filing record created by importing external AEAT evidence."""

    operation: str = "modelo.filing_record.import"
    evidence_kind: str
    evidence_reference_id: str
    filing_record_id: str
    work_unit_id: str
    calculation_revision_id: str
    bucket_id: str
    modelo: str
    filing_year: int
    period: Period
    filed_at: str
    filed_by: str
    notes: str | None = None
    aeat_accepted: bool | None = None
    status: str
    superseded_at: str | None = None
    superseded_by_filing_record_id: str | None = None
    external_evidence: ExternalEvidencePayload | None = None
    amends_filing_record_id: FilingRecordId | None = None
    kind: str = "internal_filing"
    live_submission: bool = False


@register_schema("modelo.filing_record.observe_local")
class FilingRecordLocalObservationResult(OutputSchema):
    """Local operator-supplied observation recorded for calculation prefill."""

    operation: str = "modelo.filing_record.observe_local"
    modelo: str
    filing_year: int
    period: Period
    revision_id: RevisionId
    observation_key: str
    source_kind: str
    casilla_values: dict[CasillaId, str]
    casilla_count: int
    captured_at: str
    captured_by: str
    official_evidence: bool
    filing_record_created: bool
    aeat_accepted: bool


class ModeloRowPayload(OutputSchema):
    """One modelo row in the list modelos output."""

    code: str
    title: str
    cadence: str
    tax_domain: str
    revision_count: int
    local_work_supported: bool
    local_work_status: str
    local_work_guidance: str | None = None


@register_schema("modelo.list")
class ModeloListResult(OutputSchema):
    """List modelos result."""

    operation: str = "modelo.list"
    year_filter: int | None = None
    modelo_count: int
    modelos: list[ModeloRowPayload]


@register_schema("modelo.describe")
class ModeloDescribeResult(OutputSchema):
    """Describe modelo result."""

    operation: str = "modelo.describe"
    code: str
    title: str
    official_name: str
    tax_domain: str
    cadence: str
    revision: str
    filing_year: int | None = None
    period: str | None = None
    revision_ids: list[str]
    periods: list[str]
    casilla_count: int
    binding_count: int
    formula_count: int


class CasillaRowPayload(OutputSchema):
    """One casilla row in the casillas output."""

    casilla_id: CasillaId
    number: str
    input_kind: str
    required: bool
    label: str
    localized_labels: dict[str, str] = Field(default_factory=dict)
    localized_help: dict[str, str] = Field(default_factory=dict)


@register_schema("modelo.casillas")
class ModeloCasillasResult(OutputSchema):
    """Casillas listing result."""

    operation: str = "modelo.casillas"
    modelo: str
    revision: str
    casilla_count: int
    rows: list[CasillaRowPayload]


class BindingListRowPayload(OutputSchema):
    """One binding row in the bindings list output.

    Carries the binding's regulatory grounding (``legal_refs`` /
    ``source_refs``, sourced from the registry binding definition) at
    parity with the casilla half (``CasillaRowPayload``), per the
    operator-boundary provenance-parity decision of the
    bindings-interface-hardening ADR. ``source`` renders the typed
    :class:`~aeat.core.BindingSourceKind` value as a string.
    """

    modelo: str
    revision: str
    filing_year: int | None
    period: str | None
    binding_id: BindingId
    source: str
    readiness: str
    typed_enum: str | None
    input_channel: str
    borrador_capable: bool
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


@register_schema("modelo.bindings.list")
class ModeloBindingsListResult(OutputSchema):
    """Bindings list result."""

    operation: str = "modelo.bindings.list"
    modelo_filter: str | None
    year_filter: int | None
    period_filter: str | None
    missing_filter: bool
    binding_count: int
    bindings: tuple[BindingListRowPayload, ...]


class BindingPreviewRowPayload(OutputSchema):
    """One binding preview row with optional override value.

    Carries the binding's regulatory grounding (``legal_refs`` /
    ``source_refs``, sourced from the registry binding definition) at
    parity with the casilla half, per the operator-boundary
    provenance-parity decision of the bindings-interface-hardening ADR.
    """

    binding_id: BindingId
    source: str
    readiness: str
    typed_enum: str | None
    override: str | None
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


@register_schema("modelo.bindings.resolve")
class ModeloBindingsPreviewResult(OutputSchema):
    """Bindings resolve result."""

    operation: str = "modelo.bindings.resolve"
    modelo: str
    revision: str
    filing_year: int | None
    period: str | None
    override_count: int
    binding_count: int
    bindings: list[BindingPreviewRowPayload]


# ---------------------------------------------------------------------------
# P16 – singleton verb schemas
# ---------------------------------------------------------------------------


@register_schema("modelo.export")
class ModeloExportPayload(OutputSchema):
    """Modelo export result (path reference only — no raw bytes in envelope).

    Distinct from the application :class:`ModeloExportResult` (DB-26 S51 T8):
    the backend result carries the write metadata plus an absolute ``Path`` and
    extra audit fields; this envelope projects the path-reference receipt
    (fichero-BOE bytes are never carried) using ``output_path`` (stringified),
    ``byte_size``, and ``file_sha256``. Derive instances via :meth:`from_result`.
    """

    operation: str = "modelo.export"
    work_unit_id: str
    calculation_revision_id: str
    bucket_id: str
    modelo: str
    filing_year: int
    period: Period
    output_path: str
    byte_size: int
    file_sha256: str
    format: str
    bucket_event_id: str

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
        )


class DeltaRowPayload(OutputSchema):
    """One casilla comparison row in the compare output."""

    casilla_id: CasillaId
    label: str
    section: str
    year_a_value: str
    year_b_value: str
    delta: str
    pct_change: str | None
    formula_id: str | None = None
    legal_refs: list[LegalRefId] = Field(min_length=1)
    source_refs: list[SourceRefId] = Field(min_length=1)


class CompareSectionPayload(OutputSchema):
    """One section grouping in the compare output."""

    section: str
    rows: list[DeltaRowPayload]


@register_schema("modelo.compare")
class ModeloCompareResult(OutputSchema):
    """Year-over-year modelo comparison result."""

    operation: str = "modelo.compare"
    modelo: str
    year_a: int
    year_b: int
    year_a_revision_id: str
    year_b_revision_id: str
    year_a_is_draft: bool
    year_b_is_draft: bool
    sections: list[CompareSectionPayload]
    delta_rows: list[DeltaRowPayload]


class ModeloLifecycleEventPayload(OutputSchema):
    """One bucket event in the modelo history output."""

    event_id: str
    event_type: str
    occurred_at: str
    actor: str
    object_type: str
    object_id: str
    payload: dict[str, str]


@register_schema("modelo.history")
class ModeloHistoryResult(OutputSchema):
    """Chronological modelo lifecycle history result."""

    operation: str = "modelo.history"
    modelo: str
    year: int | None
    period: str | None
    count: int
    events: list[ModeloLifecycleEventPayload]


class CasillaObservationPayload(OutputSchema):
    """One typed casilla observation in the project result."""

    casilla_id: CasillaId
    value: str
    formula_id: str | None = None
    legal_refs: list[LegalRefId] = Field(min_length=1)
    source_refs: list[SourceRefId] = Field(min_length=1)


class M130AccumulatedPayload(OutputSchema):
    """Accumulated M130 aggregation inputs for the project result."""

    ingresos: str
    gastos: str
    rendimiento_neto: str
    pagos_fraccionados: str


class M100ProjectionPayload(OutputSchema):
    """Projected M100 output casillas in the project result."""

    base_liquidable_general_0505: str
    pagos_fraccionados_0604: str
    cuota_integra_estatal_0545: str
    cuota_integra_autonomica_0546: str
    cuota_liquida_estatal_0595: str
    cuota_liquida_autonomica_0596: str
    cuota_resultante_0597: str


@register_schema("modelo.project")
class ModeloProjectResult(OutputSchema):
    """Year-end M100 projection from M130 quarterly filings."""

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


class ModeloReadinessMissingBindingPayload(OutputSchema):
    """One calculation binding readiness cannot satisfy."""

    binding_id: str
    source: str
    input_channel: str


class LedgerIssuePayload(OutputSchema):
    """One ledger issue in the readiness result."""

    transaction_id: str
    reason: str
    detail: str


@register_schema("modelo.readiness")
class ModeloReadinessResult(OutputSchema):
    """Active-profile modelo readiness report."""

    operation: str = "modelo.readiness"
    profile_id: str
    modelo: str
    revision_id: str
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


@register_schema("modelo.iva_wallet.balance")
class IvaWalletBalanceResult(OutputSchema):
    """IVA compensation carry-forward wallet balance."""

    operation: str = "modelo.iva_wallet.balance"
    as_of_year: int
    total_balance: str
    lot_count: int
    next_expiry_year: int | None
    unallocated_applied_amount: str


@register_schema("modelo.iva_wallet.seed")
class IvaWalletSeedResult(OutputSchema):
    """IVA compensation period seed confirmation."""

    operation: str = "modelo.iva_wallet.seed"
    filing_year: int
    period: Period
    taxpayer_nif: str
    amount: str
    status: str


@register_schema("modelo.iva_wallet.override")
class IvaWalletOverrideResult(OutputSchema):
    """IVA compensation taxpayer-override decision confirmation.

    Records the explicit taxpayer override that releases the Modelo 303
    cross-period compensación carry the reconciliation gate refuses to auto-apply
    without live AEAT wallet evidence. ``selected_authority`` is ``taxpayer_override``
    and ``divergence`` is ``override``; ``reason`` and ``evidence_locator`` carry the
    mandatory provenance. The override unblocks the carry CALCULATION only — it does
    not satisfy the dependent period's official-evidence verify gate.
    """

    operation: str = "modelo.iva_wallet.override"
    filing_year: int
    period: Period
    taxpayer_nif: str
    amount: str
    reason: str
    evidence_locator: str
    selected_authority: str
    divergence: str


@register_schema("modelo.work.resume")
class WorkResumeResult(OutputSchema):
    """Workflow resume precondition and context result."""

    operation: str = "modelo.work.resume"
    prior_workflow_run_id: str
    resolved_source: str | None = None
    work_unit_id: str | None = None
    short_work_unit_id: str | None = None
    calculation_revision_id: str | None = None
    short_calculation_revision_id: str | None = None
    modelo: str
    period: Period
    aborted_reason: str
    obligation: dict[str, object]


@register_schema("modelo.aggregate")
class ModeloAggregateResult(OutputSchema):
    """Per-modelo aggregation result."""

    operation: str = "modelo.aggregate"
    modelo: str
    period: Period
    provider: str
    observation_count: int
    source_kinds: list[str]
    result_row_count: int


@register_schema("modelo.work.preview_maritime_exemption")
class WorkPreviewMaritimeExemptionResult(OutputSchema):
    """Maritime worker IRPF exemption preview result."""

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
    "DeltaRowPayload",
    "EvidenceBundleCheckFindingPayload",
    "EvidenceRecordRefPayload",
    "FilingRecordImportResult",
    "FilingRecordLocalObservationResult",
    "FindingPayload",
    "FormulaPayload",
    "FormulasResult",
    "IvaWalletBalanceResult",
    "IvaWalletSeedResult",
    "LedgerIssuePayload",
    "M100ProjectionPayload",
    "M130AccumulatedPayload",
    "ModeloAggregateResult",
    "ModeloAuditCheckResult",
    "ModeloAuditExportResult",
    "ModeloAuditReplayResult",
    "ModeloAuditShowResult",
    "ModeloBindingsListResult",
    "ModeloBindingsPreviewResult",
    "ModeloCasillasResult",
    "ModeloCompareResult",
    "ModeloDescribeResult",
    "ModeloExportPayload",
    "ModeloHistoryResult",
    "ModeloLifecycleEventPayload",
    "ModeloListResult",
    "ModeloProjectResult",
    "ModeloReadinessMissingBindingPayload",
    "ModeloReadinessMissingRequirementPayload",
    "ModeloReadinessResult",
    "ModeloReconcileResult",
    "ModeloReconciliationDiffPayload",
    "ModeloRecordListResult",
    "ModeloRecordPayload",
    "ModeloRecordShowResult",
    "ModeloRowPayload",
    "ObservationPayload",
    "ResultSummaryRowPayload",
    "VerificationReportListResult",
    "VerificationReportPayload",
    "VerificationReportShowResult",
    "WorkAmendResult",
    "WorkCalculateResult",
    "WorkCompareTaxationResult",
    "WorkCreateResult",
    "WorkDependenciesResult",
    "WorkDiscardResult",
    "WorkFileResult",
    "WorkHistoryResult",
    "WorkListResult",
    "WorkPreviewMaritimeExemptionResult",
    "WorkRenameResult",
    "WorkResumeResult",
    "WorkRevisionsResult",
    "WorkRunsResult",
    "WorkStatusResult",
    "WorkUnitHistoryEventPayload",
    "WorkUnitPayload",
    "WorkVerifyResult",
    "WorkflowRunPayload",
]
