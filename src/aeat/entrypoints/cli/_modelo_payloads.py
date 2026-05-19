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


class ObservationPayload(OutputSchema):
    """One typed casilla observation with full provenance."""

    casilla_id: str
    value: str  # serialised Decimal
    formula_id: str | None = None
    operand_refs: tuple[str, ...] = ()
    operand_values: tuple[str, ...] = ()
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


class CalculationRevisionPayload(OutputSchema):
    """Calculation revision fields surfaced by calculate / revisions commands."""

    calculation_revision_id: str
    work_unit_id: str
    state: str
    casilla_values: dict[str, str]  # casilla_id → str(Decimal)
    observations: tuple[ObservationPayload, ...]
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
class WorkCreateResult(OutputSchema):
    operation: str = "modelo.work.create"
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
    calculation_revision_id: str
    work_unit_id: str
    state: str
    casilla_values: dict[str, str]
    observations: tuple[ObservationPayload, ...]
    binding_overrides: dict[str, str]
    inputs_snapshot: dict[str, object]
    created_at: str
    updated_at: str
    verified_at: str | None = None
    verified_by: str | None = None
    filed_at: str | None = None
    filed_by: str | None = None
    superseded_at: str | None = None


@register_schema("modelo.work.revisions")
class WorkRevisionsResult(OutputSchema):
    operation: str = "modelo.work.revisions"
    work_unit_id_filter: str | None = None
    revision_count: int
    revisions: list[CalculationRevisionPayload]


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
