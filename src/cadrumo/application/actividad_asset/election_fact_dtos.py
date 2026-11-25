"""Wire snapshots for the supporting facts of an amortization election."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field

from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.renta.actividad_asset.election import (
    ApprovedAmortizationPlan,
    ElectionReference,
    EvidenceReference,
    LowValueElection,
    OriginalPriceDetermination,
    PlanAnnualAmount,
    PlanApprovalKind,
    SmallEnterpriseEvidence,
    UsedAssetOriginalPrice,
)
from ..operations.public_scalar import PublicDecimal, project_scalar


class PlanAnnualAmountSnapshot(BaseModel):
    """One approved annual amount in the public wire form."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    tax_year: FilingYear
    amount: PublicDecimal

    @classmethod
    def from_domain(cls, value: PlanAnnualAmount) -> Self:
        """Project the canonical fact to its wire form."""
        return cls(tax_year=value.tax_year, amount=project_scalar(value.amount))

    def to_domain(self) -> PlanAnnualAmount:
        """Restore the canonical fact from the wire form."""
        return PlanAnnualAmount(tax_year=self.tax_year, amount=Decimal(self.amount.decimal))


class ApprovedAmortizationPlanSnapshot(BaseModel):
    """An approved amortization plan and its annual amounts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    approval_reference: ElectionReference
    approval_kind: PlanApprovalKind
    submitted_on: date
    resolved_on: date
    annual_amounts: tuple[PlanAnnualAmountSnapshot, ...] = Field(min_length=1)

    @classmethod
    def from_domain(cls, value: ApprovedAmortizationPlan) -> Self:
        """Project the canonical fact to its wire form."""
        return cls(
            approval_reference=value.approval_reference,
            approval_kind=value.approval_kind,
            submitted_on=value.submitted_on,
            resolved_on=value.resolved_on,
            annual_amounts=tuple(PlanAnnualAmountSnapshot.from_domain(item) for item in value.annual_amounts),
        )

    def to_domain(self) -> ApprovedAmortizationPlan:
        """Restore the canonical fact from the wire form."""
        return ApprovedAmortizationPlan(
            approval_reference=self.approval_reference,
            approval_kind=self.approval_kind,
            submitted_on=self.submitted_on,
            resolved_on=self.resolved_on,
            annual_amounts=tuple(item.to_domain() for item in self.annual_amounts),
        )


class SmallEnterpriseEvidenceSnapshot(BaseModel):
    """Evidence for a small enterprise election."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    evidence_reference: EvidenceReference
    made_available_on: date
    prior_period_net_turnover: PublicDecimal

    @classmethod
    def from_domain(cls, value: SmallEnterpriseEvidence) -> Self:
        """Project the canonical fact to its wire form."""
        return cls(
            evidence_reference=value.evidence_reference,
            made_available_on=value.made_available_on,
            prior_period_net_turnover=project_scalar(value.prior_period_net_turnover),
        )

    def to_domain(self) -> SmallEnterpriseEvidence:
        """Restore the canonical fact from the wire form."""
        return SmallEnterpriseEvidence(
            evidence_reference=self.evidence_reference,
            made_available_on=self.made_available_on,
            prior_period_net_turnover=Decimal(self.prior_period_net_turnover.decimal),
        )


class UsedAssetOriginalPriceSnapshot(BaseModel):
    """The original price evidence for a used asset."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    determination: OriginalPriceDetermination
    original_price: PublicDecimal
    evidence_reference: EvidenceReference | None = None

    @classmethod
    def from_domain(cls, value: UsedAssetOriginalPrice) -> Self:
        """Project the canonical fact to its wire form."""
        return cls(
            determination=value.determination,
            original_price=project_scalar(value.original_price),
            evidence_reference=value.evidence_reference,
        )

    def to_domain(self) -> UsedAssetOriginalPrice:
        """Restore the canonical fact from the wire form."""
        return UsedAssetOriginalPrice(
            determination=self.determination,
            original_price=Decimal(self.original_price.decimal),
            evidence_reference=self.evidence_reference,
        )


class LowValueElectionSnapshot(BaseModel):
    """Evidence for a low-value asset election."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    election_reference: ElectionReference
    new_material_evidence_reference: EvidenceReference

    @classmethod
    def from_domain(cls, value: LowValueElection) -> Self:
        """Project the canonical fact to its wire form."""
        return cls(
            election_reference=value.election_reference,
            new_material_evidence_reference=value.new_material_evidence_reference,
        )

    def to_domain(self) -> LowValueElection:
        """Restore the canonical fact from the wire form."""
        return LowValueElection(
            election_reference=self.election_reference,
            new_material_evidence_reference=self.new_material_evidence_reference,
        )
