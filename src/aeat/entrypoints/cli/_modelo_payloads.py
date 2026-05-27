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

from pydantic import Field

from ._schemas import OutputSchema, register_schema

# ---------------------------------------------------------------------------
# Shared sub-models (not registered — used as nested types)
# ---------------------------------------------------------------------------


class WorkUnitPayload(OutputSchema):
    """Work unit fields shared across create / status / rename / discard."""

    work_unit_id: str
    bucket_id: str
    modelo: str
    filing_year: int
    period: str
    revision_id: str
    name: str
    state: str
    created_at: str
    updated_at: str
    discarded_at: str | None = None
    discarded_by: str | None = None
    discard_reason: str | None = None
    causante_ccaa: str | None = None


class ObservationPayload(OutputSchema):
    """One typed casilla observation with full provenance."""

    casilla_id: str
    value: str  # serialised Decimal
    formula_id: str | None = None
    operand_refs: tuple[str, ...] = ()
    operand_values: tuple[str, ...] = ()
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


class ResultSummaryRowPayload(OutputSchema):
    """One headline-result summary row (registry-declared lead figure)."""

    role: str
    casilla_id: str
    value: str  # serialised Decimal
    label: str


class CalculationRevisionPayload(OutputSchema):
    """Calculation revision fields surfaced by calculate / revisions commands."""

    calculation_revision_id: str
    work_unit_id: str
    state: str
    casilla_values: dict[str, str]  # casilla_id → str(Decimal)
    observations: tuple[ObservationPayload, ...]
    # Registry-declared lead figures (result-to-pay / result-to-refund
    # plus key computed casillas) surfaced above the full casilla table.
    # Empty tuple when the modelo carries no summary mapping or the
    # revision has no values to summarise.
    result_summary: tuple[ResultSummaryRowPayload, ...] = ()
    binding_overrides: dict[str, str]
    inputs_snapshot: dict[str, object]
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
    casilla_id: str | None = None
    expectation_id: str | None = None
    message: str
    next_action: str | None = None
    legal_refs: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class VerificationReportPayload(OutputSchema):
    """Verification report fields returned by verify / verification-report commands."""

    verification_report_id: str
    calculation_revision_id: str
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
    external_evidence: ExternalEvidencePayload | None = None
    amends_filing_record_id: str | None = None
    kind: str = "internal_filing"
    live_submission: bool = False


class FormulaPayload(OutputSchema):
    """One formula row in the formulas command output."""

    formula_id: str
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
@register_schema("modelo.work.reuse")
class WorkCreateResult(OutputSchema):
    # ``operation`` is either ``modelo.work.create`` (a fresh unit was
    # created) or ``modelo.work.reuse`` (an existing unit matching the
    # natural-key tuple was returned unchanged); the same shape covers
    # both lanes so the command surface keeps a single typed contract.
    operation: str = "modelo.work.create"
    status: str
    status_message: str
    name_applied: str | None = None
    applicability_guard_bypassed: bool
    work_unit_id: str
    bucket_id: str
    modelo: str
    filing_year: int
    period: str
    revision_id: str
    name: str
    state: str
    created_at: str
    updated_at: str
    discarded_at: str | None = None
    discarded_by: str | None = None
    discard_reason: str | None = None


@register_schema("modelo.work.list")
class WorkListResult(OutputSchema):
    operation: str = "modelo.work.list"
    bucket_id_filter: str | None = None
    include_discarded: bool
    work_unit_count: int
    work_units: list[WorkUnitPayload]


@register_schema("modelo.work.status")
class WorkStatusResult(OutputSchema):
    operation: str = "modelo.work.status"
    work_unit_id: str
    bucket_id: str
    modelo: str
    filing_year: int
    period: str
    revision_id: str
    name: str
    state: str
    created_at: str
    updated_at: str
    discarded_at: str | None = None
    discarded_by: str | None = None
    discard_reason: str | None = None


@register_schema("modelo.work.rename")
class WorkRenameResult(OutputSchema):
    operation: str = "modelo.work.rename"
    work_unit_id: str
    bucket_id: str
    modelo: str
    filing_year: int
    period: str
    revision_id: str
    name: str
    state: str
    created_at: str
    updated_at: str
    discarded_at: str | None = None
    discarded_by: str | None = None
    discard_reason: str | None = None


@register_schema("modelo.work.discard")
class WorkDiscardResult(OutputSchema):
    operation: str = "modelo.work.discard"
    work_unit_id: str
    bucket_id: str
    modelo: str
    filing_year: int
    period: str
    revision_id: str
    name: str
    state: str
    created_at: str
    updated_at: str
    discarded_at: str | None = None
    discarded_by: str | None = None
    discard_reason: str | None = None


@register_schema("modelo.work.calculate")
class WorkCalculateResult(OutputSchema):
    operation: str = "modelo.work.calculate"
    # Persistence-confirmation pair surfaced by the calculate verb so JSON
    # consumers see the same signal the text-mode confirmation line carries.
    saved: bool = True
    saved_confirmation: str
    calculation_revision_id: str
    work_unit_id: str
    state: str
    casilla_values: dict[str, str]
    observations: tuple[ObservationPayload, ...]
    result_summary: tuple[ResultSummaryRowPayload, ...] = ()
    binding_overrides: dict[str, str]
    inputs_snapshot: dict[str, object]
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


@register_schema("modelo.work.revisions")
class WorkRevisionsResult(OutputSchema):
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
    calculation_revision_id: str
    work_unit_id: str
    state: str
    casilla_values: dict[str, str]
    observations: tuple[ObservationPayload, ...]
    result_summary: tuple[ResultSummaryRowPayload, ...] = ()
    binding_overrides: dict[str, str]
    inputs_snapshot: dict[str, object]
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
    operation: str = "modelo.work.verify"
    verification_report_id: str
    calculation_revision_id: str
    completeness_status: str
    granted_verificado_completo: bool
    resolved_casillas: list[str]
    missing_required_casillas: list[str]
    run_at: str
    verified_by: str
    findings: list[FindingPayload]


@register_schema("modelo.work.file")
class WorkFileResult(OutputSchema):
    operation: str = "modelo.work.file"
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


@register_schema("modelo.work.amend")
class WorkAmendResult(OutputSchema):
    operation: str = "modelo.work.amend"
    amendment_kind: str
    amends_filing_record_id: str
    # amend uses the same filing-record body as work.file but always
    # carries the amendment metadata pair above.
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


@register_schema("modelo.filing_record.list")
class ModeloRecordListResult(OutputSchema):
    operation: str = "modelo.filing_record.list"
    bucket_id_filter: str | None = None
    include_superseded: bool
    record_count: int
    records: list[ModeloRecordPayload]


@register_schema("modelo.filing_record.show")
class ModeloRecordShowResult(OutputSchema):
    operation: str = "modelo.filing_record.show"
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


@register_schema("modelo.verification_report.list")
class VerificationReportListResult(OutputSchema):
    operation: str = "modelo.verification_report.list"
    calculation_revision_id_filter: str | None = None
    report_count: int
    reports: list[VerificationReportPayload]


@register_schema("modelo.verification_report.show")
class VerificationReportShowResult(OutputSchema):
    operation: str = "modelo.verification_report.show"
    verification_report_id: str
    calculation_revision_id: str
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
    "CalculationRevisionPayload",
    "FindingPayload",
    "FormulaPayload",
    "FormulasResult",
    "ModeloRecordListResult",
    "ModeloRecordPayload",
    "ModeloRecordShowResult",
    "ObservationPayload",
    "VerificationReportListResult",
    "VerificationReportPayload",
    "VerificationReportShowResult",
    "WorkAmendResult",
    "WorkCalculateResult",
    "WorkCompareTaxationResult",
    "WorkCreateResult",
    "WorkDiscardResult",
    "WorkFileResult",
    "WorkListResult",
    "WorkRenameResult",
    "WorkRevisionsResult",
    "WorkStatusResult",
    "WorkUnitPayload",
    "WorkVerifyResult",
]
