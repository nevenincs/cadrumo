"""Auxiliary modelo payload schemas split from the main modelo registry.

These strict :class:`OutputSchema` subclasses
are registered through :func:`register_schema`
and re-exported by :mod:`_modelo_payloads` so audit,
work-history, workflow-run, list, and describe emitters keep one payload import
surface. Validated results enter
:class:`SchemaEnvelope` through
:func:`_emit_envelope`.

The application/modelo, workflow, and audit services remain authoritative for
evidence-bundle manifests, work-unit event history, workflow runs, and modelo
catalogue metadata; this module only pins CLI transport shapes.
"""

from __future__ import annotations

from ...core.aggregation import RetencionClave
from ._schemas import OutputSchema, register_schema


class WithholdingClaveBreakdownPayload(OutputSchema):
    """One per-clave retención row of the Modelo 190 reconciliation breakdown.

    JSON projection of
    :class:`WithholdingClaveBreakdown`: the
    ``clave`` keeps its typed :class:`RetencionClave`
    member (the closed AEAT clave-de-percepción axis) and the magnitudes are
    rendered as canonical decimal strings. Re-exported through
    :mod:`_modelo_payloads` so the
    :class:`ModeloAggregateResult`
    envelope can carry the breakdown that lets an operator reconcile the annual
    Modelo 190 retención totals against the per-clave figures of the individual
    Modelo 111 quarterly filings.
    """

    clave: RetencionClave
    percepcion_count: int
    percibido_total: str
    retencion_total: str


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
    """One :class:`WorkflowResult` row in the runs listing."""

    run_id: str
    modelo: str | None
    period: str | None
    final_stage: str
    aborted_reason: str | None
    started_at: str
    summary: str
    next_action: str | None


@register_schema("modelo.work.runs")
class WorkRunsResult(OutputSchema):
    """Workflow run listing returned by ``aeat app modelo work runs``.

    Rows mirror persisted :class:`WorkflowResult` records discovered through
    :func:`list_runs`.
    """

    operation: str = "modelo.work.runs"
    run_count: int
    runs: list[WorkflowRunPayload]


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
    domain_filter: str | None = None
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
