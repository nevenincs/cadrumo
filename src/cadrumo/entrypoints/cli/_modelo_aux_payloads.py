"""Auxiliary modelo payload schemas split from the main modelo registry.

These strict :class:`OutputSchema` subclasses
are referenced as deferred public schema targets by production-authored CommandSpec
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

from datetime import date, datetime
from typing import Annotated

from pydantic import Field

from ...application.evidence import BundleVerificationState
from ...application.workflow import (
    SiteHealthAlert,
    WorkflowObligationFacts,
    WorkflowStage,
    WorkflowStepDetails,
)
from ...core import Hex64Str, Period
from ...core.aggregation import RetencionClave
from ...core.identity import BucketId, CalculationRevisionId, ContentDigest, FilingRecordId, WorkUnitId
from ...core.json_contract import OutputSchema, ResolvedPreconditionAction
from ...domain.buckets import (
    BucketActorLabel,
    BucketEventId,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.calculations.registry import LegalRefId, ModeloDescribeReport, SourceRefId
from ._decimal_wire import NonNegativeDecimalWireText


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
    percepcion_count: int = Field(ge=0)
    percibido_total: NonNegativeDecimalWireText
    retencion_total: NonNegativeDecimalWireText


class EvidenceRecordRefPayload(OutputSchema):
    """One record reference entry inside an evidence bundle manifest.

    JSON projection of :class:`EvidenceRecordRef`. ``content_sha256`` keeps
    the canonical :data:`~core.identity.ContentDigest` constraint the record
    carries, so the machine-facing boundary cannot emit a digest the
    application model would refuse.
    """

    object_type: BucketEventObjectType
    object_id: str = Field(min_length=1, max_length=128)
    content_sha256: ContentDigest
    payload_size_bytes: int = Field(ge=0)


class EvidenceBundleCheckFindingPayload(OutputSchema):
    """One check outcome from a bundle verification pass."""

    check: str
    passed: bool
    detail: str = ""


class ModeloAuditShowResult(OutputSchema):
    """Evidence bundle manifest render result (audit show)."""

    operation: str = "modelo.audit.show"
    bundle_id: Hex64Str
    manifest_version: int = Field(ge=1)
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId | None = None
    filing_record_id: FilingRecordId | None = None
    verification_state: BundleVerificationState
    completeness_ratio: float = Field(ge=0.0, le=1.0)
    records: list[EvidenceRecordRefPayload]
    created_at: datetime
    notes: str = Field(default="", max_length=2000)


class ModeloAuditCheckResult(OutputSchema):
    """Evidence bundle integrity re-verification result (audit check)."""

    operation: str = "modelo.audit.check"
    bundle_id: Hex64Str
    verification_state: BundleVerificationState
    completeness_ratio: float = Field(ge=0.0, le=1.0)
    findings: list[EvidenceBundleCheckFindingPayload]


class ModeloAuditExportResult(OutputSchema):
    """Evidence bundle ZIP export result (audit export).

    Uses output path reference + record count instead of raw bytes so
    the JSON envelope never persists binary content.
    """

    operation: str = "modelo.audit.export"
    bucket_id: BucketId
    bundle_id: Hex64Str
    output: str = Field(min_length=1)
    verification_state: BundleVerificationState
    records: int = Field(ge=0)


class WorkUnitHistoryEventPayload(OutputSchema):
    """One event row in a work-unit history stream."""

    event_id: BucketEventId
    occurred_at: datetime
    event_type: BucketEventType
    object_type: BucketEventObjectType
    object_id: str = Field(min_length=1, max_length=128)
    actor: BucketActorLabel
    payload: dict[str, str]


class WorkHistoryResult(OutputSchema):
    """Work-unit event history result."""

    operation: str = "modelo.work.history"
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    event_count: int
    events: list[WorkUnitHistoryEventPayload]


class WorkflowRunPayload(OutputSchema):
    """One localized view of a locale-neutral persisted workflow run.

    The human summary is derived only at this transport boundary. Its stable
    source key and closed typed facts remain visible beside the canonical
    schema-resolved action DTO; no persisted prose or free-form recovery
    instruction crosses into this payload.
    """

    run_id: str
    modelo: str | None
    period: str | None
    final_stage: str
    aborted_reason: str | None
    started_at: str
    obligation: WorkflowObligationFacts | None
    summary_stage: WorkflowStage | None
    summary_locale_key: str = Field(
        pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$",
        min_length=3,
        max_length=160,
    )
    summary_details: WorkflowStepDetails | None = None
    site_health_alert: SiteHealthAlert | None = None
    summary: str
    action: ResolvedPreconditionAction | None = None


class WorkRunsResult(OutputSchema):
    """Workflow run listing returned by the ``modelo.work.runs`` leaf.

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


class ModeloListResult(OutputSchema):
    """List modelos result."""

    operation: str = "modelo.list"
    year_filter: int | None = None
    domain_filter: str | None = None
    modelo_count: int
    modelos: list[ModeloRowPayload]


class ModeloDescribeResult(OutputSchema):
    """Describe modelo result.

    Complete JSON projection of
    :class:`ModeloDescribeReport`. The
    payload carries every field of the canonical report -- including the
    ``jurisdiction``, the revision validity bounds, the per-input-kind casilla
    counts, and the ``legal_refs`` / ``source_refs`` grounding -- because an
    operator justifying a revision selection needs the same evidence the domain
    report holds. Build instances through :meth:`from_report` rather than
    field-by-field, so a field added to the report cannot silently stop at this
    boundary.
    """

    operation: str = "modelo.describe"
    code: str
    title: str
    official_name: str
    tax_domain: str
    cadence: str
    jurisdiction: str
    revision: str
    filing_year: Annotated[int, Field(ge=1980, le=2200)] | None = None
    filing_period: Period | None = None
    period: str | None = None
    revision_ids: list[str]
    periods: list[str]
    valid_from: date
    valid_to: date | None = None
    casilla_count: int = Field(ge=0)
    manual_casilla_count: int = Field(ge=0)
    bound_casilla_count: int = Field(ge=0)
    computed_casilla_count: int = Field(ge=0)
    binding_count: int = Field(ge=0)
    formula_count: int = Field(ge=0)
    legal_refs: list[LegalRefId] = Field(default_factory=list)
    source_refs: list[SourceRefId] = Field(default_factory=list)

    @classmethod
    def from_report(cls, report: ModeloDescribeReport) -> ModeloDescribeResult:
        """Project every field of a canonical describe report into the envelope.

        Args:
            report: The domain-layer describe report to render.

        Returns:
            The strict CLI payload carrying the report's full field set.
        """
        return cls(
            code=report.code,
            title=report.title,
            official_name=report.official_name,
            tax_domain=report.tax_domain,
            cadence=report.cadence,
            jurisdiction=report.jurisdiction,
            revision=report.revision,
            filing_year=report.filing_year,
            filing_period=report.filing_period,
            period=report.period,
            revision_ids=list(report.revision_ids),
            periods=list(report.periods),
            valid_from=report.valid_from,
            valid_to=report.valid_to,
            casilla_count=report.casilla_count,
            manual_casilla_count=report.manual_casilla_count,
            bound_casilla_count=report.bound_casilla_count,
            computed_casilla_count=report.computed_casilla_count,
            binding_count=report.binding_count,
            formula_count=report.formula_count,
            legal_refs=list(report.legal_refs),
            source_refs=list(report.source_refs),
        )
