"""Closed snapshots for persisted workflow filing-obligation facts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, model_validator

from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.deadlines.models import ObligationStatus
from ..operations.public_period import PublicPeriod
from ..operations.public_scalar import PublicDecimal
from .run_models import WorkflowDeadlineRecoveryFacts, WorkflowObligationFacts


class WorkflowDeadlineRecoverySnapshot(BaseModel):
    """Schema-safe legal and amount facts for one overdue obligation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    still_filable: bool
    recargo_band_id: str
    min_completed_months: int = Field(ge=0)
    max_completed_months: int | None = Field(default=None, ge=0)
    surcharge_pct: PublicDecimal
    interest_applies: bool
    legal_ref: str

    @classmethod
    def from_recovery(cls, recovery: WorkflowDeadlineRecoveryFacts) -> Self:
        """Copy a validated canonical recovery record."""
        return cls(
            still_filable=recovery.still_filable,
            recargo_band_id=recovery.recargo_band_id,
            min_completed_months=recovery.min_completed_months,
            max_completed_months=recovery.max_completed_months,
            surcharge_pct=PublicDecimal(decimal=str(recovery.surcharge_pct)),
            interest_applies=recovery.interest_applies,
            legal_ref=recovery.legal_ref,
        )

    def to_recovery(self) -> WorkflowDeadlineRecoveryFacts:
        """Restore and validate the canonical recovery invariant."""
        return WorkflowDeadlineRecoveryFacts(
            still_filable=self.still_filable,
            recargo_band_id=self.recargo_band_id,
            min_completed_months=self.min_completed_months,
            max_completed_months=self.max_completed_months,
            surcharge_pct=Decimal(self.surcharge_pct.decimal),
            interest_applies=self.interest_applies,
            legal_ref=self.legal_ref,
        )

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_recovery()
        return self


class WorkflowObligationSnapshot(BaseModel):
    """Lossless public-schema copy of canonical filing obligation facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    modelo: str
    period: PublicPeriod
    opens_on: date
    closes_on: date
    payment_cutoff_on: date | None = None
    status: ObligationStatus
    boe_references: tuple[str, ...] = ()
    recovery: WorkflowDeadlineRecoverySnapshot | None = None

    @classmethod
    def from_obligation(cls, obligation: WorkflowObligationFacts) -> Self:
        """Copy persisted obligation facts without prose or raw commands."""
        return cls(
            modelo=str(obligation.modelo),
            period=PublicPeriod.from_period(obligation.period),
            opens_on=obligation.opens_on,
            closes_on=obligation.closes_on,
            payment_cutoff_on=obligation.payment_cutoff_on,
            status=obligation.status,
            boe_references=obligation.boe_references,
            recovery=(
                WorkflowDeadlineRecoverySnapshot.from_recovery(obligation.recovery)
                if obligation.recovery is not None
                else None
            ),
        )

    def to_obligation(self) -> WorkflowObligationFacts:
        """Reconstruct the canonical obligation for existing resume/render code."""
        return WorkflowObligationFacts(
            modelo=Modelo(self.modelo),
            period=self.period.to_period(),
            opens_on=self.opens_on,
            closes_on=self.closes_on,
            payment_cutoff_on=self.payment_cutoff_on,
            status=self.status,
            boe_references=self.boe_references,
            recovery=self.recovery.to_recovery() if self.recovery is not None else None,
        )

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_obligation()
        return self


__all__ = ["WorkflowDeadlineRecoverySnapshot", "WorkflowObligationSnapshot"]
