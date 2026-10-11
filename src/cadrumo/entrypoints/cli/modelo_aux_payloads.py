"""Auxiliary modelo payload schemas split from the main modelo registry.

These strict :class:`OutputSchema` subclasses
are referenced as deferred public schema targets by production-authored CommandSpec
and re-exported by :mod:`_modelo_payloads` so audit, work-history and
workflow-run emitters keep one payload import surface. Validated results enter
:class:`SchemaEnvelope` through
:func:`emit_envelope`.

The application/modelo, workflow, and audit services remain authoritative for
evidence-bundle manifests, work-unit event history and workflow runs; this
module only pins CLI transport shapes.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import NonNegativeInt

from ...application.evidence.bundle_text import EvidenceBundleNotes
from ...application.evidence.models import BundleVerificationState
from ...application.evidence.payloads import EvidenceRecordRefPayload
from ...application.workflow.run_models import (
    SiteHealthAlert,
    WorkflowObligationFacts,
    WorkflowStage,
    WorkflowStepDetails,
)
from ...core.aggregation import RetencionClave
from ...core.hex import Hex64Str
from ...core.identifier_grammar import NamespacedId
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId, WorkUnitId
from ...core.json_contract import OutputSchema, ResolvedPreconditionAction
from ...core.text_bounds import NonEmptyStr, PositiveCount
from ...core.unit_proportion import UnitFraction
from ...domain.buckets.event import (
    BucketActorLabel,
    BucketEventId,
    BucketEventObjectType,
    BucketEventType,
    BucketObjectId,
)
from ._decimal_wire import NonNegativeDecimalWireText


class WithholdingClaveBreakdownPayload(OutputSchema):
    """One per-clave retención row of an annual withholding summary's reconciliation breakdown.

    JSON projection of
    :class:`WithholdingClaveBreakdown`: the
    ``clave`` keeps its typed, registry-projected :class:`RetencionClave`
    token (the AEAT clave-de-percepción axis) and the magnitudes are
    rendered as canonical decimal strings. Re-exported through
    :mod:`_modelo_payloads` so the
    :class:`ModeloAggregateResult`
    envelope can carry the breakdown that lets an operator reconcile an annual
    summary's retención totals, such as Modelo 190's, against the per-clave
    figures of the periodic filings its calculation reads.
    """

    clave: RetencionClave
    percepcion_count: NonNegativeInt
    percibido_total: NonNegativeDecimalWireText
    retencion_total: NonNegativeDecimalWireText


class EvidenceBundleCheckFindingPayload(OutputSchema):
    """One check outcome from a bundle verification pass."""

    check: str
    passed: bool
    detail: str = ""


class ModeloAuditViewResult(OutputSchema):
    """Evidence bundle manifest render result (audit show)."""

    operation: str = "modelo.audit.show"
    bundle_id: Hex64Str
    manifest_version: PositiveCount
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId | None = None
    filing_record_id: FilingRecordId | None = None
    verification_state: BundleVerificationState
    completeness_ratio: UnitFraction
    records: list[EvidenceRecordRefPayload]
    created_at: datetime
    notes: EvidenceBundleNotes = ""


class ModeloAuditCheckResult(OutputSchema):
    """Evidence bundle integrity re-verification result (audit check)."""

    operation: str = "modelo.audit.check"
    bundle_id: Hex64Str
    verification_state: BundleVerificationState
    completeness_ratio: UnitFraction
    findings: list[EvidenceBundleCheckFindingPayload]


class ModeloAuditExportResult(OutputSchema):
    """Evidence bundle ZIP export result (audit export).

    Uses output path reference + record count instead of raw bytes so
    the JSON envelope never persists binary content.
    """

    operation: str = "modelo.audit.export"
    bucket_id: BucketId
    bundle_id: Hex64Str
    output: NonEmptyStr
    verification_state: BundleVerificationState
    records: NonNegativeInt


class WorkUnitHistoryEventPayload(OutputSchema):
    """One event row in a work-unit history stream."""

    event_id: BucketEventId
    occurred_at: datetime
    event_type: BucketEventType
    object_type: BucketEventObjectType
    object_id: BucketObjectId
    actor: BucketActorLabel
    payload: dict[str, str]


class WorkHistoryResult(OutputSchema):
    """Work-unit event history result."""

    operation: str = "modelo.work.history"
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    event_count: int
    events: list[WorkUnitHistoryEventPayload]


class WorkflowRunSummaryPayload(OutputSchema):
    """Compact workflow-run row returned by ``modelo.work.runs``."""

    run_id: str
    modelo: str | None
    period: str | None
    final_stage: str
    aborted_reason: str | None
    started_at: str
    summary: str
    action: ResolvedPreconditionAction | None = None


class WorkflowRunPayload(WorkflowRunSummaryPayload):
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
    summary_locale_key: NamespacedId
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
    runs: list[WorkflowRunSummaryPayload]


class WorkRunResult(OutputSchema):
    """Detailed persisted workflow run returned by ``modelo.work.run``.

    Nested obligation and site-health records are flattened so this singular
    read preserves their operator-relevant facts without advertising their
    unrelated recursive schema graphs.
    """

    operation: str = "modelo.work.run"
    run_id: str
    modelo: str | None
    period: str | None
    final_stage: str
    aborted_reason: str | None
    started_at: str
    obligation_opens_on: str | None = None
    obligation_closes_on: str | None = None
    obligation_status: str | None = None
    summary_stage: WorkflowStage | None
    summary_locale_key: NamespacedId
    site_health_stage: str | None = None
    site_health_state: str | None = None
    site_health_observed_at: str | None = None
    site_health_http_status: int | None = None
    site_health_retry_after_seconds: int | None = None
    site_health_detected_marker_count: int | None = None
    summary: str
    action: ResolvedPreconditionAction | None = None


class WorkRunDetailsResult(OutputSchema):
    """Bounded terminal-step facts for one persisted workflow run.

    Values retain the persisted JSON primitives while ``kind`` remains the
    discriminator operators use to interpret the closed workflow detail shape.
    """

    operation: str = "modelo.work.run_details"
    run_id: str
    summary_stage: WorkflowStage | None
    summary_locale_key: NamespacedId
    summary_detail_kind: str | None = None
    summary_detail_facts: dict[str, str | int | bool | list[str] | None] | None = None
