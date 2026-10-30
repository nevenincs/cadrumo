"""Operation snapshots for acquisition, opening history, and asset basis facts."""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, model_validator

from ...application.operations.public_scalar import PublicDecimal, project_scalar
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.hex import Hex64Str
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.renta.actividad_asset.election import AmortizationMethod
from ...domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    AssetBasisStage,
    FurtherAcquisitionRow,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
    OwnershipMode,
)


def _decimal(value: PublicDecimal | None) -> Decimal | None:
    return None if value is None else Decimal(value.decimal)


class AcquisitionLineageSnapshot(BaseModel):
    """Acquisition evidence at the operation boundary."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    observed_transaction_id: TransactionId | None = None
    observed_lineage_event_id: Hex64Str | None = None
    invoice_evidence_id: str = Field(max_length=256)
    evidence_fingerprint: Hex64Str | None = None

    @classmethod
    def from_domain(cls, value: AcquisitionLineageReference) -> Self:
        """Project the domain facts into the wire representation."""
        return cls(**value.model_dump(mode="python"))

    def to_domain(self) -> AcquisitionLineageReference:
        """Restore the validated domain facts."""
        return AcquisitionLineageReference(**self.model_dump(mode="python"))


class FurtherAcquisitionSnapshot(BaseModel):
    """A further acquisition row at the operation boundary."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    shape: AcquisitionShape
    lineage: AcquisitionLineageSnapshot

    @classmethod
    def from_domain(cls, value: FurtherAcquisitionRow) -> Self:
        """Project the domain facts into the wire representation."""
        return cls(shape=value.shape, lineage=AcquisitionLineageSnapshot.from_domain(value.lineage))

    def to_domain(self) -> FurtherAcquisitionRow:
        """Restore the validated domain facts."""
        return FurtherAcquisitionRow(shape=self.shape, lineage=self.lineage.to_domain())


class OpeningHistorySnapshot(BaseModel):
    """Opening amortization history at the operation boundary."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    status: OpeningHistoryStatus
    accumulated_amount: PublicDecimal | None = None
    amortization_method: AmortizationMethod | None = None
    covered_through_tax_year: FilingYear | None = None

    @classmethod
    def from_domain(cls, value: OpeningAmortizationHistory) -> Self:
        """Project the domain facts into the wire representation."""
        return cls(
            status=value.status,
            accumulated_amount=(
                project_scalar(value.accumulated_amount) if value.accumulated_amount is not None else None
            ),
            amortization_method=value.amortization_method,
            covered_through_tax_year=value.covered_through_tax_year,
        )

    def to_domain(self) -> OpeningAmortizationHistory:
        """Restore the validated domain facts."""
        return OpeningAmortizationHistory(
            status=self.status,
            accumulated_amount=_decimal(self.accumulated_amount),
            amortization_method=self.amortization_method,
            covered_through_tax_year=self.covered_through_tax_year,
        )

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _canonical(self) -> Self:
        self.to_domain()
        return self


class ActivityAssetBasisSnapshot(BaseModel):
    """Public basis DTO with explicit decimal allocation facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    stage: AssetBasisStage
    basis_amount: PublicDecimal
    non_deductible_iva: PublicDecimal
    is_property: bool = False
    construction_cost: PublicDecimal | None = None
    land_cost: PublicDecimal | None = None
    ownership_mode: OwnershipMode | None = None
    ownership_share: PublicDecimal | None = None
    office_area: PublicDecimal | None = None
    total_area: PublicDecimal | None = None
    business_use_share: PublicDecimal | None = None
    prior_allocation_provenance: str | None = Field(default=None, min_length=1, max_length=512)

    @classmethod
    def from_domain(cls, value: ActivityAssetBasis) -> Self:
        """Copy a canonical basis into its public decimal representation."""
        decimal_names = (
            "basis_amount",
            "non_deductible_iva",
            "construction_cost",
            "land_cost",
            "ownership_share",
            "office_area",
            "total_area",
            "business_use_share",
        )
        data = value.model_dump(mode="python")
        for name in decimal_names:
            amount = data[name]
            data[name] = PublicDecimal(decimal=str(amount)) if amount is not None else None
        return cls(**data)

    def to_domain(self) -> ActivityAssetBasis:
        """Restore and revalidate the canonical domain basis."""
        return ActivityAssetBasis(
            stage=self.stage,
            basis_amount=Decimal(self.basis_amount.decimal),
            non_deductible_iva=Decimal(self.non_deductible_iva.decimal),
            is_property=self.is_property,
            construction_cost=_decimal(self.construction_cost),
            land_cost=_decimal(self.land_cost),
            ownership_mode=self.ownership_mode,
            ownership_share=_decimal(self.ownership_share),
            office_area=_decimal(self.office_area),
            total_area=_decimal(self.total_area),
            business_use_share=_decimal(self.business_use_share),
            prior_allocation_provenance=self.prior_allocation_provenance,
        )

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _canonical(self) -> Self:
        self.to_domain()
        return self
