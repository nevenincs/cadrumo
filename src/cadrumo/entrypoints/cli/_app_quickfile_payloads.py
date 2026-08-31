"""Typed ``--json`` payload schema for the ``aeat app quickfile`` envelope.

Projects the application :class:`~application.modelo.QuickfileResult` onto a
strict :class:`~core.json_contract.OutputSchema` referenced as a deferred public target under the
``quickfile`` command path. The per-stage outcomes and the terminal export
receipt (path reference only — never raw fichero bytes) are surfaced so a machine
consumer can read exactly which stage the chain reached and where it halted.
"""

from __future__ import annotations

from ...application.modelo._export import ModeloExportResult
from ...application.modelo._quickfile import (
    QuickfileResult,
    QuickfileStage,
    QuickfileStageStatus,
)
from ...application.state_projection import ProjectionModeloReadiness
from ...core.identity import BucketId, CalculationRevisionId, WorkUnitId
from ...core.json_contract import OutputSchema
from ...core.payment_election import PaymentElection
from ...core.period import Period
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ...core.result_disposition import ResultDisposition
from ...domain.calculations.registry.ids import RevisionId


class QuickfileReadinessSummaryPayload(OutputSchema):
    """Compact verdict for the advisory quickfile readiness stage."""

    ready: bool
    profile_ready: bool
    registry_ready: bool
    binding_ready: bool
    ledger_preflight_required: bool
    ledger_ready: bool | None
    missing_profile_fact_count: int
    missing_binding_count: int
    ledger_issue_count: int

    @classmethod
    def from_result(cls, result: ProjectionModeloReadiness) -> QuickfileReadinessSummaryPayload:
        """Summarise every readiness axis without embedding its large diagnostic tree."""
        return cls(
            ready=result.ready,
            profile_ready=result.profile_ready,
            registry_ready=result.registry_ready,
            binding_ready=result.binding_ready,
            ledger_preflight_required=result.ledger_preflight_required,
            ledger_ready=result.ledger_ready,
            missing_profile_fact_count=len(result.missing),
            missing_binding_count=len(result.missing_bindings),
            ledger_issue_count=len(result.ledger_issues),
        )


class QuickfileExportSummaryPayload(OutputSchema):
    """Compact terminal export receipt with identity and file-integrity facts."""

    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    bucket_id: BucketId
    bucket_event_id: str
    output_path: str
    byte_size: int
    file_sha256: str
    format: str
    resolved_result_disposition: ResultDisposition
    payment_election: PaymentElection | None = None
    refund_election: RefundElection | None = None
    prior_domiciliation_election: PriorDomiciliationElection

    @classmethod
    def from_result(cls, result: ModeloExportResult) -> QuickfileExportSummaryPayload:
        """Project the terminal receipt without duplicating the filing target tree."""
        return cls(
            work_unit_id=result.work_unit_id,
            calculation_revision_id=result.calculation_revision_id,
            bucket_id=result.bucket_id,
            bucket_event_id=result.bucket_event_id,
            output_path=str(result.output_path),
            byte_size=result.byte_size,
            file_sha256=result.file_sha256,
            format=result.format,
            resolved_result_disposition=result.resolved_result_disposition,
            payment_election=result.payment_election,
            refund_election=result.refund_election,
            prior_domiciliation_election=result.prior_domiciliation_election.election,
        )


class QuickfileStageOutcomePayload(OutputSchema):
    """One quickfile stage's outcome projected for the JSON envelope.

    ``stage`` and ``status`` reuse the canonical
    :class:`~application.modelo.QuickfileStage` and
    :class:`~application.modelo.QuickfileStageStatus` enums the application
    layer owns, so an unknown stage or status is refused at the transport
    boundary rather than crossing it as an opaque string. Both are
    ``StrEnum`` members and therefore still serialise to their string form.
    ``context`` carries the stage's structured refs (work-unit id, revision
    id, refusal counts) verbatim.
    """

    stage: QuickfileStage
    status: QuickfileStageStatus
    message: str = ""
    context: dict[str, str] = {}


class QuickfileResultPayload(OutputSchema):
    """Aggregate ``aeat app quickfile`` result envelope.

    ``completed`` is true only when the terminal local fichero-BOE export
    succeeded. ``stopped_at_stage`` names the stage that refused when the chain
    halted early. ``export`` is the path-reference export receipt (never raw
    bytes) and is ``None`` when the chain stopped before export. ``readiness``
    summarises the readiness-check stage (``None`` when that stage never ran),
    retaining each axis verdict and blocker counts without embedding the large
    diagnostic action tree.
    """

    operation: str = "quickfile"
    modelo: str
    filing_year: int
    period: Period
    registry_revision_id: RevisionId
    completed: bool
    stopped_at_stage: QuickfileStage | None = None
    readiness: QuickfileReadinessSummaryPayload | None = None
    work_unit_id: WorkUnitId | None = None
    calculation_revision_id: CalculationRevisionId | None = None
    granted_verificado_completo: bool | None = None
    export: QuickfileExportSummaryPayload | None = None
    stages: tuple[QuickfileStageOutcomePayload, ...]

    @classmethod
    def from_result(cls, result: QuickfileResult) -> QuickfileResultPayload:
        """Project the application :class:`QuickfileResult` into this :class:`QuickfileResultPayload` envelope."""
        granted = result.verification_report.granted_verificado_completo if result.verification_report else None
        return cls(
            modelo=result.modelo,
            filing_year=result.filing_year,
            period=result.period,
            registry_revision_id=result.registry_revision_id,
            completed=result.completed,
            stopped_at_stage=result.stopped_at_stage,
            readiness=(
                QuickfileReadinessSummaryPayload.from_result(result.readiness) if result.readiness is not None else None
            ),
            work_unit_id=result.work_unit.work_unit_id if result.work_unit is not None else None,
            calculation_revision_id=(
                result.calculation_revision.calculation_revision_id if result.calculation_revision is not None else None
            ),
            granted_verificado_completo=granted,
            export=(
                QuickfileExportSummaryPayload.from_result(result.export_result)
                if result.export_result is not None
                else None
            ),
            stages=tuple(
                QuickfileStageOutcomePayload(
                    stage=outcome.stage,
                    status=outcome.status,
                    message=outcome.message,
                    context=dict(outcome.context),
                )
                for outcome in result.stages
            ),
        )


__all__ = [
    "QuickfileExportSummaryPayload",
    "QuickfileReadinessSummaryPayload",
    "QuickfileResultPayload",
    "QuickfileStageOutcomePayload",
]
