"""Typed ``--json`` payload schemas for modelo work-lifecycle commands.

Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract test suite can
enumerate every command surface this module covers.

Field set is additive: legacy callers continue to read the same payload
shape they always did, while new clients see the additional typed-
provenance fields (``observations``, ``legal_refs``, ``source_refs``,
``schema_version``, ``command``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from ...core.identity import BucketId
from ...domain.calculations.registry import (
    CasillaId,
    FormulaId,
    RevisionId,
)
from ...domain.modelos._ids import (
    CalculationRevisionId,
    FilingRecordId,
    VerificationReportId,
    WorkUnitId,
)
from ._schemas import OutputSchema, register_schema

if TYPE_CHECKING:
    from ...application.modelo import ModeloExportResult as _AppModeloExportResult

# ---------------------------------------------------------------------------
# Shared sub-models (not registered — used as nested types)
# ---------------------------------------------------------------------------


class WorkUnitPayload(OutputSchema):
    """Work unit fields shared across create / status / rename / discard."""

    work_unit_id: WorkUnitId
    short_work_unit_id: str
    bucket_id: BucketId
    modelo: str
    filing_year: int
    period: str
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
    operand_values: tuple[str, ...] = ()
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


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
    casilla_values: dict[str, str]  # casilla_id → str(Decimal)
    observations: tuple[ObservationPayload, ...]
    # Registry-declared lead figures (result-to-pay / result-to-refund
    # plus key computed casillas) surfaced above the full casilla table.
    # Empty tuple when the modelo carries no summary mapping or the
    # revision has no values to summarise.
    result_summary: tuple[ResultSummaryRowPayload, ...] = ()
    binding_overrides: dict[str, str]
    inputs_snapshot: dict[str, str]
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


class VerificationReportPayload(OutputSchema):
    """Verification report fields returned by verify / verification-report commands."""

    verification_report_id: VerificationReportId
    calculation_revision_id: CalculationRevisionId
    completeness_status: str
    granted_verificado_completo: bool
    resolved_casillas: list[str]
    missing_required_casillas: list[str]
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
    period: str
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
    target: str
    input_casillas: tuple[str, ...]
    input_bindings: tuple[str, ...]
    input_parameters: tuple[str, ...]
    input_relations: tuple[str, ...]
    expression: dict[str, object]
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


# ---------------------------------------------------------------------------
# Registered command-level schemas
# ---------------------------------------------------------------------------


@register_schema("modelo.work.create")
class WorkCreateResult(OutputSchema):
    # ``operation`` is either ``modelo.work.create`` (a fresh unit was
    # created) or ``modelo.work.reuse`` (an existing unit matching the
    # natural-key tuple was returned unchanged); the same shape covers
    # both lanes so the command surface keeps a single typed contract
    # and a single envelope-registry key.
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
    period: str
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
    period: str
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
    period: str
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
    period: str
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
    # Persistence-confirmation pair surfaced by the calculate verb so JSON
    # consumers see the same signal the text-mode confirmation line carries.
    saved: bool = True
    saved_confirmation: str
    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    state: str
    casilla_values: dict[str, str]
    observations: tuple[ObservationPayload, ...]
    result_summary: tuple[ResultSummaryRowPayload, ...] = ()
    binding_overrides: dict[str, str]
    inputs_snapshot: dict[str, str]
    created_at: str
    updated_at: str
    verified_at: str | None = None
    verified_by: str | None = None
    filed_at: str | None = None
    filed_by: str | None = None
    superseded_at: str | None = None
    # Modelo 202 pago-fraccionado modality (Art. 40.2 vs 40.3 lane).
    # Populated only when the underlying work unit is modelo 202; other
    # modelos leave these unset.
    modality: str | None = None
    modality_reason: str | None = None
    # Backend authorization lifecycle state. Populated when the modelo's
    # calculation backend is UNAUTHORIZED (not yet proven across >=2 renta
    # years per the modelo-multiyear-renta gate) but an engine exists, so the
    # calculation still ran. The accompanying advisory prose is surfaced on
    # the envelope ``notices`` channel, not as a bespoke payload field.
    authorization_state: str | None = None


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
    casilla_values: dict[str, str]
    observations: tuple[ObservationPayload, ...]
    result_summary: tuple[ResultSummaryRowPayload, ...] = ()
    binding_overrides: dict[str, str]
    inputs_snapshot: dict[str, str]
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
    resolved_casillas: list[str]
    missing_required_casillas: list[str]
    run_at: str
    verified_by: str
    findings: list[FindingPayload]


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
    period: str
    filed_at: str
    filed_by: str
    notes: str | None = None
    aeat_accepted: bool | None = None
    status: str
    superseded_at: str | None = None
    superseded_by_filing_record_id: FilingRecordId | None = None
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
    # amend uses the same filing-record body as work.file but always
    # carries the amendment metadata pair above.
    filing_record_id: FilingRecordId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    bucket_id: BucketId
    modelo: str
    filing_year: int
    period: str
    filed_at: str
    filed_by: str
    notes: str | None = None
    aeat_accepted: bool | None = None
    status: str
    superseded_at: str | None = None
    superseded_by_filing_record_id: FilingRecordId | None = None
    kind: str = "internal_filing"
    live_submission: bool = False


@register_schema("modelo.filing_record.list")
class ModeloRecordListResult(OutputSchema):
    """Filing-record listing returned by ``aeat app modelo filing-record list``."""

    operation: str = "modelo.filing_record.list"
    bucket_id_filter: str | None = None
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
    period: str
    filed_at: str
    filed_by: str
    notes: str | None = None
    aeat_accepted: bool | None = None
    status: str
    superseded_at: str | None = None
    superseded_by_filing_record_id: FilingRecordId | None = None
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
    resolved_casillas: list[str]
    missing_required_casillas: list[str]
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


# ---------------------------------------------------------------------------
# P13 – audit / history verb schemas
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# P14 – record-query verb schemas (schemas for list/show already existed)
# ---------------------------------------------------------------------------


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
    period: str
    filed_at: str
    filed_by: str
    notes: str | None = None
    aeat_accepted: bool | None = None
    status: str
    superseded_at: str | None = None
    superseded_by_filing_record_id: str | None = None
    kind: str = "internal_filing"
    live_submission: bool = False


# ---------------------------------------------------------------------------
# P15 – registry-projection verb schemas
# ---------------------------------------------------------------------------


class ModeloRowPayload(OutputSchema):
    """One modelo row in the list modelos output."""

    code: str
    title: str
    cadence: str
    tax_domain: str
    revision_count: int


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

    casilla_id: str
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


class BindingRowPayload(OutputSchema):
    """One binding row in the bindings list/preview output."""

    modelo: str
    revision: str
    filing_year: int | None
    period: str | None
    binding_id: str
    source: str
    readiness: str
    typed_enum: str | None
    input_channel: str
    borrador_capable: bool


@register_schema("modelo.bindings.list")
class ModeloBindingsListResult(OutputSchema):
    """Bindings list result."""

    operation: str = "modelo.bindings.list"
    modelo_filter: str | None
    year_filter: int | None
    period_filter: str | None
    missing_filter: bool
    binding_count: int
    bindings: list[dict[str, object]]


class BindingPreviewRowPayload(OutputSchema):
    """One binding preview row with optional override value."""

    binding_id: str
    source: str
    readiness: str
    typed_enum: str | None
    override: str | None


@register_schema("modelo.bindings.preview")
class ModeloBindingsPreviewResult(OutputSchema):
    """Bindings preview result."""

    operation: str = "modelo.bindings.preview"
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
    period: str
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

    casilla_id: str
    label: str
    section: str
    year_a_value: str
    year_b_value: str
    delta: str
    pct_change: str | None
    formula_id: str | None = None
    legal_refs: list[str] = []
    source_refs: list[str] = []


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

    casilla_id: str
    value: str
    formula_id: str | None = None
    legal_refs: list[str] = []
    source_refs: list[str] = []


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
    period: str
    ready: bool
    profile_ready: bool
    missing: list[ModeloReadinessMissingRequirementPayload]
    ledger_preflight_required: bool
    ledger_ready: bool | None
    ledger_period: str | None
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
    period: str
    taxpayer_nif: str
    amount: str
    status: str


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
    period: str
    aborted_reason: str
    obligation: dict[str, object]


@register_schema("modelo.aggregate")
class ModeloAggregateResult(OutputSchema):
    """Per-modelo aggregation result."""

    operation: str = "modelo.aggregate"
    modelo: str
    period: str
    provider: str
    observation_count: int
    source_kinds: list[str]
    result_row_count: int


@register_schema("modelo.work.preview_maritime_exemption")
class WorkPreviewMaritimeExemptionResult(OutputSchema):
    """Result payload for ``aeat app modelo work preview-maritime-exemption``.

    Surfaces the maritime worker IRPF exemption resolution for the active
    profile: typed CasillaObservation rows carrying ``legal_refs`` and
    ``source_refs`` (the canonical contract per aeat-calculation-grounding)
    alongside a flat ``casilla_values`` projection for human readability.

    The ``retmar_mandatory_filing`` flag mirrors the RETMAR completeness
    gate: when ``True`` the operator is informed via the RETMAR warning
    message that all RETMAR-registered workers must file IRPF regardless
    of income level (Ley 47/2015 BOE-A-2015-11346). The DA 41 inactive
    refusal raises ``MaritimeExemptionInactiveError`` and is rendered
    through the CLI error boundary; this payload is not emitted in that
    branch.
    """

    operation: str = "modelo.work.preview_maritime_exemption"
    worker_class: str | None = None
    vessel_flag: str | None = None
    waters_type: str | None = None
    vessel_registry: str | None = None
    retmar_registered: bool = False
    retmar_mandatory_filing: bool = False
    retmar_warning: str | None = None
    casilla_values: dict[str, str] = Field(default_factory=dict)
    observations: list[CasillaObservationPayload] = Field(default_factory=list)


class ModeloReconciliationDiffPayload(OutputSchema):
    """One per-casilla disagreement surfaced in a reconciliation report."""

    field_name: str
    work_unit_value: str = ""
    evidence_value: str = ""
    kind: str


@register_schema("modelo.reconcile")
@register_schema("modelo.reconcile_from_justificante")
class ModeloReconcileResult(OutputSchema):
    """Result payload for ``modelo reconcile`` and ``reconcile-from-justificante``.

    Both verbs share the :class:`ModeloReconciliationReport` shape from
    the application service: a work-unit-level verdict, the bucket
    scope, the external-evidence source kind and path, the per-casilla
    diff list, the reconciliation timestamp, and an optional narrative.
    """

    work_unit_id: WorkUnitId
    bucket_id: BucketId
    source_kind: str
    source_path: str
    verdict: str
    diffs: tuple[ModeloReconciliationDiffPayload, ...] = ()
    reconciled_at: str
    narrative: str = ""


@register_schema("modelo.work.compare_taxation")
class WorkCompareTaxationResult(OutputSchema):
    """Result payload for ``aeat app modelo work compare-taxation``.

    Surfaces cuota resultante autoliquidación (0595) and cuota
    diferencial / resultado (0610) for both conjunta and individual
    filing modes, plus the delta and recommendation.
    """

    operation: str = "modelo.work.compare_taxation"
    filing_year: int
    modelo: str
    revision: str
    conjunta_cuota_resultante: str
    individual_cuota_resultante: str
    conjunta_resultado: str
    individual_resultado: str
    delta_resultado: str
    recommendation: str
    recommendation_reason: str


__all__ = [
    "BindingPreviewRowPayload",
    "BindingRowPayload",
    "CalculationRevisionPayload",
    "CasillaObservationPayload",
    "CasillaRowPayload",
    "CompareSectionPayload",
    "DeltaRowPayload",
    "EvidenceBundleCheckFindingPayload",
    "EvidenceRecordRefPayload",
    "FilingRecordImportResult",
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
