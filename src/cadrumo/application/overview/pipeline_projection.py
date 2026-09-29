"""Closed JSON snapshots of the canonical pipeline health read model."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from pydantic import BaseModel, NonNegativeInt, model_validator

from ...core.identity.hex_ids import WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..ledger.models import LedgerStatusReport
from ..modelo.verification_projection import ModeloArgumentSnapshot
from ..operations.public_period import PublicPeriod
from ..operator_actions.models import ActionReference, DeclaredNextAction
from .pipeline_health import ModeloHealthRow, ModeloReadinessState, PipelineHealthReport


class PipelineLedgerSnapshot(BaseModel):
    """Ledger summary facts without domain-specific period serialization."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    business_income_total: str
    business_expense_total: str
    business_net_total: str
    total_count: NonNegativeInt
    active_count: NonNegativeInt
    archived_count: NonNegativeInt
    stashed_count: NonNegativeInt
    split_count: NonNegativeInt
    pending_review_count: NonNegativeInt
    reviewed_count: NonNegativeInt
    skipped_count: NonNegativeInt
    checked_transaction_count: NonNegativeInt
    readiness_issue_count: NonNegativeInt
    unconverted_currency_count: NonNegativeInt
    ready: bool | None

    @classmethod
    def from_report(cls, report: LedgerStatusReport) -> Self:
        """Copy existing counters and decimal text, without recomputing totals."""
        return cls.model_validate(report.model_dump(exclude={"bucket_id", "period"}))

    def to_report(self, *, profile_id: UUID, period: PublicPeriod) -> LedgerStatusReport:
        """Restore the canonical report using the containing exact scope."""
        return LedgerStatusReport.model_validate(
            self.model_dump() | {"bucket_id": str(profile_id), "period": period.to_period()}
        )


class PipelineNextActionSnapshot(BaseModel):
    """Preserve one declared next action with scalar-safe argument facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: ActionReference
    argument_bindings: tuple[ModeloArgumentSnapshot, ...] = ()

    @classmethod
    def from_action(cls, action: DeclaredNextAction) -> Self:
        """Project canonical action arguments without flattening Decimal values."""
        return cls(
            action=action.action,
            argument_bindings=tuple(
                ModeloArgumentSnapshot.from_argument(argument) for argument in action.argument_bindings
            ),
        )

    def to_action(self) -> DeclaredNextAction:
        """Restore and revalidate one canonical declared action."""
        return DeclaredNextAction(
            action=self.action,
            argument_bindings=tuple(argument.to_argument() for argument in self.argument_bindings),
        )

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        """Reject invalid provenance or unresolved arguments before release."""
        self.to_action()
        return self


class PipelineModeloHealthSnapshot(BaseModel):
    """Closed transport form of one canonical modelo readiness row."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: str
    work_unit_id: WorkUnitId | None = None
    state: ModeloReadinessState
    blocking_finding_count: NonNegativeInt = 0
    warning_finding_count: NonNegativeInt = 0
    summary: str
    next_action: PipelineNextActionSnapshot | None = None

    @classmethod
    def from_row(cls, row: ModeloHealthRow) -> Self:
        """Copy canonical readiness while converting only action scalar values."""
        return cls(
            modelo=row.modelo,
            work_unit_id=row.work_unit_id,
            state=row.state,
            blocking_finding_count=row.blocking_finding_count,
            warning_finding_count=row.warning_finding_count,
            summary=row.summary,
            next_action=PipelineNextActionSnapshot.from_action(row.next_action)
            if row.next_action is not None
            else None,
        )

    def to_row(self) -> ModeloHealthRow:
        """Restore the canonical row and its validated declared action."""
        return ModeloHealthRow(
            modelo=self.modelo,
            work_unit_id=self.work_unit_id,
            state=self.state,
            blocking_finding_count=self.blocking_finding_count,
            warning_finding_count=self.warning_finding_count,
            summary=self.summary,
            next_action=self.next_action.to_action() if self.next_action is not None else None,
        )


class PipelineHealthSnapshot(BaseModel):
    """One profile's period health, including its whole-profile ledger counts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    period: PublicPeriod
    ledger: PipelineLedgerSnapshot
    modelos: tuple[PipelineModeloHealthSnapshot, ...]
    total_blocking_findings: NonNegativeInt
    total_warning_findings: NonNegativeInt
    ready: bool

    @model_validator(mode="after")
    def _unique_units(self) -> Self:
        ids = [item.work_unit_id for item in self.modelos if item.work_unit_id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("pipeline rows repeat a work unit")
        return self

    @classmethod
    def from_report(cls, report: PipelineHealthReport) -> Self:
        """Preserve the builder's scope, findings, actions and readiness verdict."""
        period = report.ledger.period
        if period is None or report.ledger.bucket_id != report.bucket_id:
            raise ValueError("pipeline ledger lacks its exact profile and period")
        if report.filing_year != period.filing_year or report.period != period.registry_token:
            raise ValueError("pipeline report and ledger periods differ")
        return cls(
            profile_id=UUID(report.bucket_id),
            period=PublicPeriod.from_period(period),
            ledger=PipelineLedgerSnapshot.from_report(report.ledger),
            modelos=tuple(PipelineModeloHealthSnapshot.from_row(item) for item in report.modelos),
            total_blocking_findings=report.total_blocking_findings,
            total_warning_findings=report.total_warning_findings,
            ready=report.ready,
        )

    def to_report(self) -> PipelineHealthReport:
        """Rehydrate only the report that was captured by the worker."""
        period = self.period.to_period()
        return PipelineHealthReport(
            bucket_id=str(self.profile_id),
            filing_year=period.filing_year,
            period=period.registry_token,
            ledger=self.ledger.to_report(profile_id=self.profile_id, period=self.period),
            modelos=tuple(item.to_row() for item in self.modelos),
            total_blocking_findings=self.total_blocking_findings,
            total_warning_findings=self.total_warning_findings,
            ready=self.ready,
        )
