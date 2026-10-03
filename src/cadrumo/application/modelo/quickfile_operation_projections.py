"""Canonical public result projection for the human quickfile operation."""

from __future__ import annotations

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.errors.error_codes import get_registered_error_code
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect
from ...domain.modelos.verification_report import ModeloVerificationFindingSeverity
from ..operations.public_period import PublicPeriod
from ..operator_actions.projection import PreconditionVerdictSnapshot
from .export_projection import ModeloFicheroBoePublicReceipt
from .quickfile import (
    QUICKFILE_STAGE_ORDER,
    QuickfileResult,
    QuickfileStage,
    QuickfileStageOutcome,
    QuickfileStageStatus,
)
from .quickfile_operation_contracts import (
    QuickfileReadinessSummary,
    QuickfileReference,
    QuickfileStageError,
    QuickfileStageFacts,
    QuickfileStageMessage,
    QuickfileStageSnapshot,
)
from .verification_projection import ModeloVerificationReportSnapshot


class QuickfileProjection(BaseModel):
    """Complete current human outputs and an authoritative whole-chain effect receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    profile_id: UUID
    operation: Literal["quickfile"] = "quickfile"
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")]
    filing_year: int
    period: PublicPeriod
    registry_revision_id: Annotated[str, Field(max_length=128)]
    completed: bool
    stopped_at_stage: QuickfileStage | None
    readiness: QuickfileReadinessSummary | None
    work_unit_id: QuickfileReference | None
    calculation_revision_id: QuickfileReference | None
    verification_report: ModeloVerificationReportSnapshot | None
    export: ModeloFicheroBoePublicReceipt | None
    stages: tuple[QuickfileStageSnapshot, ...]
    write_count: Annotated[int, Field(ge=0)]
    effect: OperationEffect

    @model_validator(mode="after")
    def _canonical_chain(self) -> Self:
        _require_canonical_order(self)
        _require_period_year(self)
        _require_completion_consistency(self)
        _require_stopped_stage_consistency(self)
        _require_export_target(self)
        _require_verification_target(self)
        _require_effect_consistency(self)
        return self

    @classmethod
    def from_result(
        cls, result: QuickfileResult, *, profile_id: UUID, write_count: int, effect: OperationEffect
    ) -> Self:
        """Project canonical results, deriving facts without persisting arbitrary exception context."""
        summary = _readiness_summary(result)
        stages = tuple(_stage_snapshot(result, outcome) for outcome in result.stages)
        return cls(
            profile_id=profile_id,
            modelo=result.modelo,
            filing_year=result.filing_year,
            period=PublicPeriod.from_period(result.period),
            registry_revision_id=result.registry_revision_id,
            completed=result.completed,
            stopped_at_stage=result.stopped_at_stage,
            readiness=summary,
            work_unit_id=result.work_unit.work_unit_id if result.work_unit is not None else None,
            calculation_revision_id=result.calculation_revision.calculation_revision_id
            if result.calculation_revision is not None
            else None,
            verification_report=ModeloVerificationReportSnapshot.from_report(result.verification_report)
            if result.verification_report is not None
            else None,
            export=ModeloFicheroBoePublicReceipt.from_result(result.export_result)
            if result.export_result is not None
            else None,
            stages=stages,
            write_count=write_count,
            effect=effect,
        )


def _require_canonical_order(projection: QuickfileProjection) -> None:
    if tuple(row.stage for row in projection.stages) != QUICKFILE_STAGE_ORDER:
        raise ValueError("quickfile must retain every canonical stage in order")


def _require_period_year(projection: QuickfileProjection) -> None:
    if projection.filing_year != projection.period.to_period().filing_year:
        raise ValueError("quickfile filing year must match its natural period")


def _require_completion_consistency(projection: QuickfileProjection) -> None:
    if not projection.completed:
        return
    _require_terminal_export(projection)
    _require_completed_statuses(projection)


def _require_terminal_export(projection: QuickfileProjection) -> None:
    refused = tuple(row.stage for row in projection.stages if row.status is QuickfileStageStatus.REFUSED)
    if projection.stopped_at_stage is not None or refused or projection.export is None:
        raise ValueError("completed quickfile requires its terminal export")
    if projection.write_count == 0:
        raise ValueError("completed quickfile requires its confirmed local export writes")


def _require_completed_statuses(projection: QuickfileProjection) -> None:
    if projection.stages[0].status not in {QuickfileStageStatus.OK, QuickfileStageStatus.WARNING} or any(
        row.status is not QuickfileStageStatus.OK for row in projection.stages[1:]
    ):
        raise ValueError("completed quickfile requires every canonical stage to finish")


def _require_stopped_stage_consistency(projection: QuickfileProjection) -> None:
    refused = tuple(row.stage for row in projection.stages if row.status is QuickfileStageStatus.REFUSED)
    if not projection.completed and refused != (projection.stopped_at_stage,):
        raise ValueError("stopped quickfile requires one refused stage")
    if projection.stopped_at_stage is None:
        return
    stop = QUICKFILE_STAGE_ORDER.index(projection.stopped_at_stage)
    _require_no_early_stop(projection.stages[:stop])
    _require_skipped_after_stop(projection.stages[stop + 1 :])


def _require_no_early_stop(stages: tuple[QuickfileStageSnapshot, ...]) -> None:
    if any(row.status in {QuickfileStageStatus.REFUSED, QuickfileStageStatus.SKIPPED} for row in stages):
        raise ValueError("quickfile cannot skip a stage before its refusal")


def _require_skipped_after_stop(stages: tuple[QuickfileStageSnapshot, ...]) -> None:
    if any(row.status is not QuickfileStageStatus.SKIPPED for row in stages):
        raise ValueError("quickfile stages after refusal must remain skipped")


def _require_export_target(projection: QuickfileProjection) -> None:
    export = projection.export
    if export is None:
        return
    if (
        export.bucket_id != str(projection.profile_id)
        or export.modelo != projection.modelo
        or export.period != projection.period
        or export.output_path != projection.stages[-1].facts.output_path
        or export.work_unit_id != projection.work_unit_id
        or export.calculation_revision_id != projection.calculation_revision_id
    ):
        raise ValueError("quickfile export belongs to another target")


def _require_verification_target(projection: QuickfileProjection) -> None:
    if projection.verification_report is not None and (
        projection.verification_report.calculation_revision_id != projection.calculation_revision_id
    ):
        raise ValueError("quickfile verification belongs to another calculation")


def _require_effect_consistency(projection: QuickfileProjection) -> None:
    if (projection.write_count == 0 and projection.effect in {OperationEffect.UPDATED, OperationEffect.PARTIAL}) or (
        projection.write_count > 0 and projection.effect is OperationEffect.NONE
    ):
        raise ValueError("quickfile effect contradicts confirmed writes")
    if projection.effect is OperationEffect.UPDATED and not projection.completed:
        raise ValueError("a stopped quickfile must retain its incomplete-chain effect")


def _readiness_summary(result: QuickfileResult) -> QuickfileReadinessSummary | None:
    readiness = result.readiness
    if readiness is None:
        return None
    return QuickfileReadinessSummary(
        ready=readiness.ready,
        profile_ready=readiness.profile_ready,
        registry_ready=readiness.registry_ready,
        binding_ready=readiness.binding_ready,
        ledger_preflight_required=readiness.ledger_preflight_required,
        ledger_ready=readiness.ledger_ready,
        missing_profile_fact_count=len(readiness.missing),
        missing_binding_count=len(readiness.missing_bindings),
        ledger_issue_count=len(readiness.ledger_issues),
    )


def _stage_snapshot(result: QuickfileResult, outcome: QuickfileStageOutcome) -> QuickfileStageSnapshot:
    facts, message = _stage_facts_and_message(result, outcome)
    code = get_registered_error_code(outcome.refusal) if outcome.refusal is not None else None
    return QuickfileStageSnapshot(
        stage=outcome.stage,
        status=outcome.status,
        message=message,
        facts=facts,
        error=QuickfileStageError(code=code.code, message_key=code.message_key) if code is not None else None,
        precondition_verdict=PreconditionVerdictSnapshot.from_verdict(outcome.precondition_verdict)
        if outcome.precondition_verdict is not None
        else None,
    )


def _stage_facts_and_message(
    result: QuickfileResult, outcome: QuickfileStageOutcome
) -> tuple[QuickfileStageFacts, QuickfileStageMessage]:
    if outcome.refusal is not None:
        return QuickfileStageFacts(), ""
    if outcome.stage is QuickfileStage.READINESS:
        return _readiness_stage_projection(result, outcome)
    if outcome.stage is QuickfileStage.CREATE:
        return _create_stage_projection(result, outcome)
    if outcome.stage is QuickfileStage.CALCULATE:
        return _calculation_stage_projection(result)
    if outcome.stage is QuickfileStage.VERIFY:
        return _verification_stage_projection(result)
    if outcome.stage is QuickfileStage.EXPORT:
        return _export_stage_projection(result)
    return QuickfileStageFacts(), ""


def _readiness_stage_projection(
    result: QuickfileResult, outcome: QuickfileStageOutcome
) -> tuple[QuickfileStageFacts, QuickfileStageMessage]:
    if outcome.status is QuickfileStageStatus.WARNING:
        return _readiness_facts_and_message(result)
    return QuickfileStageFacts(), ""


def _create_stage_projection(
    result: QuickfileResult, outcome: QuickfileStageOutcome
) -> tuple[QuickfileStageFacts, QuickfileStageMessage]:
    if result.work_unit is None:
        return QuickfileStageFacts(), ""
    message = "resumed" if outcome.message == "resumed" else "created"
    return QuickfileStageFacts(work_unit_id=result.work_unit.work_unit_id), message


def _calculation_stage_projection(result: QuickfileResult) -> tuple[QuickfileStageFacts, QuickfileStageMessage]:
    return _calculation_facts(result), ""


def _verification_stage_projection(
    result: QuickfileResult,
) -> tuple[QuickfileStageFacts, QuickfileStageMessage]:
    return _verification_facts_and_message(result)


def _export_stage_projection(result: QuickfileResult) -> tuple[QuickfileStageFacts, QuickfileStageMessage]:
    return _export_facts(result), ""


def _readiness_facts_and_message(result: QuickfileResult) -> tuple[QuickfileStageFacts, QuickfileStageMessage]:
    readiness = result.readiness
    if readiness is None:
        return QuickfileStageFacts(), "readiness could not be resolved; proceeding to calculate"
    facts = QuickfileStageFacts(
        ready=False,
        profile_ready=readiness.profile_ready,
        binding_ready=readiness.binding_ready,
        missing_bindings=len(readiness.missing_bindings),
    )
    return facts, "profile is not yet source-ready; caller-supplied inputs may still satisfy calculate"


def _calculation_facts(result: QuickfileResult) -> QuickfileStageFacts:
    revision = result.calculation_revision
    if revision is None:
        return QuickfileStageFacts()
    return QuickfileStageFacts(calculation_revision_id=revision.calculation_revision_id)


def _verification_facts_and_message(result: QuickfileResult) -> tuple[QuickfileStageFacts, QuickfileStageMessage]:
    report = result.verification_report
    if report is None:
        return QuickfileStageFacts(), ""
    blocking_count = (
        sum(row.severity is ModeloVerificationFindingSeverity.BLOCKING for row in report.findings)
        if not report.granted_verificado_completo
        else None
    )
    facts = QuickfileStageFacts(
        verification_report_id=report.verification_report_id,
        granted_verificado_completo=report.granted_verificado_completo,
        blocking_finding_count=blocking_count,
    )
    message: QuickfileStageMessage = (
        "verification did not grant verificado-completo" if not report.granted_verificado_completo else ""
    )
    return facts, message


def _export_facts(result: QuickfileResult) -> QuickfileStageFacts:
    export_result = result.export_result
    if export_result is None:
        return QuickfileStageFacts()
    return QuickfileStageFacts(output_path=str(export_result.output_path), file_sha256=export_result.file_sha256)
