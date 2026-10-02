"""Closed human quickfile inputs and canonical stage/result snapshots.

Exception messages and arbitrary exception context never become operation operands.
The human presenter resolves declared stage error codes and typed recovery evidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.errors.error_codes import get_registered_error_code, get_registered_error_code_by_code
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect
from ...core.payment_election import PaymentElection
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ...domain.modelos.verification_report import ModeloVerificationFindingSeverity
from ..operations.public_period import PublicPeriod
from ..operator_actions.projection import PreconditionVerdictSnapshot
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from .calculation_request_fields import ModeloCalculationInputFieldsV1, ModeloCalculationOverride
from .export_projection import ModeloFicheroBoePublicReceipt
from .operation_definitions import ModeloDetailRowWireV1, ModeloWorkCalculateOrdinaryM303EvidenceRequestV2
from .quickfile import QUICKFILE_STAGE_ORDER, QuickfileResult, QuickfileStage, QuickfileStageStatus
from .verification_projection import ModeloVerificationReportSnapshot

type QuickfileText = Annotated[str, Field(max_length=PROJECTION_DOCUMENT_MAX_BYTES)]
type QuickfileReference = Annotated[str, Field(min_length=1, max_length=128)]


class QuickfileCalculationInputs(BaseModel):
    """Only the three scalar input channels the current quickfile command exposes."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    casilla_overrides: tuple[ModeloCalculationOverride, ...] = Field(default=(), max_length=20_000)
    binding_overrides: tuple[ModeloCalculationOverride, ...] = Field(default=(), max_length=20_000)
    relation_overrides: tuple[ModeloCalculationOverride, ...] = Field(default=(), max_length=20_000)

    def to_calculation_fields(self) -> ModeloCalculationInputFieldsV1:
        """Reuse the registered grammar and canonical calculation-input assembly."""
        return ModeloCalculationInputFieldsV1(
            casilla_overrides=self.casilla_overrides,
            binding_overrides=self.binding_overrides,
            relation_overrides=self.relation_overrides,
        )

    @model_validator(mode="after")
    def _canonical_channels(self) -> Self:
        self.to_calculation_fields()
        return self


class QuickfileRequest(BaseModel):
    """One exact profile and natural filing target, retained in encrypted custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    bucket_id: UUID | None = None
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")]
    period: PublicPeriod
    revision_id: QuickfileReference | None = None
    output_path: Annotated[str, Field(min_length=1, max_length=4096, pattern=r"\S")]
    actor: Annotated[str, Field(min_length=1, max_length=128, pattern=r"\S")]
    refund_election: RefundElection = RefundElection.COMPENSAR
    payment_election: PaymentElection = PaymentElection.INGRESO
    prior_domiciliation_election: PriorDomiciliationElection = PriorDomiciliationElection.KEEP
    ordinary_m303_filing_evidence: ModeloWorkCalculateOrdinaryM303EvidenceRequestV2 | None = None
    inputs: QuickfileCalculationInputs = QuickfileCalculationInputs()
    detail_rows: tuple[ModeloDetailRowWireV1, ...] = Field(default=(), max_length=20_000)

    @model_validator(mode="after")
    def _local_destination(self) -> Self:
        if not Path(self.output_path).is_absolute():
            raise ValueError("quickfile output path must be absolute")
        self.period.to_period()
        return self


class QuickfileReadinessSummary(BaseModel):
    """Every axis and blocker count shown by the existing human JSON output."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    ready: bool
    profile_ready: bool
    registry_ready: bool
    binding_ready: bool
    ledger_preflight_required: bool
    ledger_ready: bool | None
    missing_profile_fact_count: Annotated[int, Field(ge=0)]
    missing_binding_count: Annotated[int, Field(ge=0)]
    ledger_issue_count: Annotated[int, Field(ge=0)]


class QuickfileStageError(BaseModel):
    """A registry identity, without original exception text, arguments or context."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    code: QuickfileReference
    message_key: Annotated[str, Field(min_length=1, max_length=256)]

    @model_validator(mode="after")
    def _declared_error(self) -> Self:
        if get_registered_error_code_by_code(self.code).message_key != self.message_key:
            raise ValueError("quickfile stage error must match the declared registry row")
        return self


class QuickfileStageFacts(BaseModel):
    """Only the fixed stage facts produced by the canonical quickfile orchestrator."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    work_unit_id: QuickfileReference | None = None
    calculation_revision_id: QuickfileReference | None = None
    verification_report_id: QuickfileReference | None = None
    ready: bool | None = None
    profile_ready: bool | None = None
    binding_ready: bool | None = None
    missing_bindings: Annotated[int, Field(ge=0)] | None = None
    granted_verificado_completo: bool | None = None
    blocking_finding_count: Annotated[int, Field(ge=0)] | None = None
    output_path: QuickfileText | None = None
    file_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None

    def to_context(self) -> dict[str, str]:
        """Restore the existing stage context spelling from these declared fields."""
        declared: dict[str, str | int | bool | None] = {
            "work_unit_id": self.work_unit_id,
            "calculation_revision_id": self.calculation_revision_id,
            "verification_report_id": self.verification_report_id,
            "ready": self.ready,
            "profile_ready": self.profile_ready,
            "binding_ready": self.binding_ready,
            "missing_bindings": self.missing_bindings,
            "granted_verificado_completo": self.granted_verificado_completo,
            "blocking_finding_count": self.blocking_finding_count,
            "output_path": self.output_path,
            "file_sha256": self.file_sha256,
        }
        return {
            name: str(value).lower() if isinstance(value, bool) else str(value)
            for name, value in declared.items()
            if value is not None
        }


type QuickfileStageMessage = Literal[
    "",
    "resumed",
    "created",
    "verification did not grant verificado-completo",
    "readiness could not be resolved; proceeding to calculate",
    "profile is not yet source-ready; caller-supplied inputs may still satisfy calculate",
]


class QuickfileStageSnapshot(BaseModel):
    """An ordered canonical status, fixed message, closed facts and recovery verdict."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    stage: QuickfileStage
    status: QuickfileStageStatus
    message: QuickfileStageMessage = ""
    facts: QuickfileStageFacts = QuickfileStageFacts()
    error: QuickfileStageError | None = None
    precondition_verdict: PreconditionVerdictSnapshot | None = None


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
        if tuple(row.stage for row in self.stages) != QUICKFILE_STAGE_ORDER:
            raise ValueError("quickfile must retain every canonical stage in order")
        if self.filing_year != self.period.to_period().filing_year:
            raise ValueError("quickfile filing year must match its natural period")
        refused = tuple(row.stage for row in self.stages if row.status is QuickfileStageStatus.REFUSED)
        if self.completed:
            if self.stopped_at_stage is not None or refused or self.export is None:
                raise ValueError("completed quickfile requires its terminal export")
            if self.write_count == 0:
                raise ValueError("completed quickfile requires its confirmed local export writes")
            if self.stages[0].status not in {QuickfileStageStatus.OK, QuickfileStageStatus.WARNING} or any(
                row.status is not QuickfileStageStatus.OK for row in self.stages[1:]
            ):
                raise ValueError("completed quickfile requires every canonical stage to finish")
        elif refused != (self.stopped_at_stage,):
            raise ValueError("stopped quickfile requires one refused stage")
        if self.stopped_at_stage is not None:
            stop = QUICKFILE_STAGE_ORDER.index(self.stopped_at_stage)
            if any(
                row.status in {QuickfileStageStatus.REFUSED, QuickfileStageStatus.SKIPPED} for row in self.stages[:stop]
            ):
                raise ValueError("quickfile cannot skip a stage before its refusal")
            if any(row.status is not QuickfileStageStatus.SKIPPED for row in self.stages[stop + 1 :]):
                raise ValueError("quickfile stages after refusal must remain skipped")
        if self.export is not None and (
            self.export.bucket_id != str(self.profile_id)
            or self.export.modelo != self.modelo
            or self.export.period != self.period
            or self.export.output_path != self.stages[-1].facts.output_path
            or self.export.work_unit_id != self.work_unit_id
            or self.export.calculation_revision_id != self.calculation_revision_id
        ):
            raise ValueError("quickfile export belongs to another target")
        if self.verification_report is not None and (
            self.verification_report.calculation_revision_id != self.calculation_revision_id
        ):
            raise ValueError("quickfile verification belongs to another calculation")
        if (self.write_count == 0 and self.effect in {OperationEffect.UPDATED, OperationEffect.PARTIAL}) or (
            self.write_count > 0 and self.effect is OperationEffect.NONE
        ):
            raise ValueError("quickfile effect contradicts confirmed writes")
        if self.effect is OperationEffect.UPDATED and not self.completed:
            raise ValueError("a stopped quickfile must retain its incomplete-chain effect")
        return self

    @classmethod
    def from_result(
        cls, result: QuickfileResult, *, profile_id: UUID, write_count: int, effect: OperationEffect
    ) -> Self:
        """Project canonical results, deriving facts without persisting arbitrary exception context."""
        readiness = result.readiness
        summary = (
            QuickfileReadinessSummary(
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
            if readiness is not None
            else None
        )
        stages: list[QuickfileStageSnapshot] = []
        for outcome in result.stages:
            facts = QuickfileStageFacts()
            message: QuickfileStageMessage = ""
            if outcome.refusal is None:
                if outcome.stage is QuickfileStage.READINESS and outcome.status is QuickfileStageStatus.WARNING:
                    if readiness is None:
                        message = "readiness could not be resolved; proceeding to calculate"
                    else:
                        message = "profile is not yet source-ready; caller-supplied inputs may still satisfy calculate"
                        facts = QuickfileStageFacts(
                            ready=False,
                            profile_ready=readiness.profile_ready,
                            binding_ready=readiness.binding_ready,
                            missing_bindings=len(readiness.missing_bindings),
                        )
                elif outcome.stage is QuickfileStage.CREATE and result.work_unit is not None:
                    message = "resumed" if outcome.message == "resumed" else "created"
                    facts = QuickfileStageFacts(work_unit_id=result.work_unit.work_unit_id)
                elif outcome.stage is QuickfileStage.CALCULATE and result.calculation_revision is not None:
                    facts = QuickfileStageFacts(
                        calculation_revision_id=result.calculation_revision.calculation_revision_id
                    )
                elif outcome.stage is QuickfileStage.VERIFY and result.verification_report is not None:
                    report = result.verification_report
                    facts = QuickfileStageFacts(
                        verification_report_id=report.verification_report_id,
                        granted_verificado_completo=report.granted_verificado_completo,
                        blocking_finding_count=sum(
                            row.severity is ModeloVerificationFindingSeverity.BLOCKING for row in report.findings
                        )
                        if not report.granted_verificado_completo
                        else None,
                    )
                    if not report.granted_verificado_completo:
                        message = "verification did not grant verificado-completo"
                elif outcome.stage is QuickfileStage.EXPORT and result.export_result is not None:
                    facts = QuickfileStageFacts(
                        output_path=str(result.export_result.output_path), file_sha256=result.export_result.file_sha256
                    )
            code = get_registered_error_code(outcome.refusal) if outcome.refusal is not None else None
            stages.append(
                QuickfileStageSnapshot(
                    stage=outcome.stage,
                    status=outcome.status,
                    message=message,
                    facts=facts,
                    error=QuickfileStageError(code=code.code, message_key=code.message_key)
                    if code is not None
                    else None,
                    precondition_verdict=PreconditionVerdictSnapshot.from_verdict(outcome.precondition_verdict)
                    if outcome.precondition_verdict is not None
                    else None,
                )
            )
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
            stages=tuple(stages),
            write_count=write_count,
            effect=effect,
        )
