"""Operator input contracts shared by modelo delivery workflows."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ...core.payment_election import PaymentElection
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from .selectors import ModeloCalculationRevisionSelector


class ModeloExportOperatorInput(BaseModel):
    """Canonical operator input required to resolve and export a modelo."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_unit_id: str | None = None
    modelo: str | None = None
    year: int | None = None
    period: str | None = None
    registry_revision: str | None = None
    bucket_id: str | None = None
    select: str = ModeloCalculationRevisionSelector.CURRENT.value
    output: Path | None = None
    revision: str | None = None
    actor: str | None = None
    refund_election: RefundElection = RefundElection.COMPENSAR
    payment_election: PaymentElection = PaymentElection.INGRESO
    prior_domiciliation_election: PriorDomiciliationElection = PriorDomiciliationElection.KEEP


class ModeloReviewPackageBuildOperatorInput(ModeloExportOperatorInput):
    """Canonical export input plus review-package annotations."""

    notes: str = ""


__all__ = ["ModeloExportOperatorInput", "ModeloReviewPackageBuildOperatorInput"]
