"""Immutable IRPF activity-asset facts and acquisition lineage."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.hashing import content_hash_hex
from ....core.models import STRICT_FROZEN_CONFIG
from .election import AcquiredCondition, ActivityAssetAmortizationElection
from .errors import ActividadAssetUnsupportedError, ActividadAssetValidationError


class AssetKind(StrEnum):
    """The two materially distinct 2025 IRPF amortization destinations."""

    MATERIAL = "material"
    INTANGIBLE = "intangible"


class AcquisitionShape(StrEnum):
    """Acquisition evidence shapes understood by the initial lifecycle."""

    PRIMARY_PURCHASE = "primary_purchase"
    SPLIT_PAYMENT = "split_payment"
    ANCILLARY_COST = "ancillary_cost"
    PRODUCED = "produced"
    HISTORICAL_WITHOUT_EVIDENCE = "historical_without_evidence"


class OwnershipMode(StrEnum):
    """Legal ownership treatments for whole-property allocation."""

    SOLE = "sole"
    FRACTIONAL_DIRECT = "fractional_direct"
    SPOUSAL_COMMUNITY = "spousal_community"


class OpeningHistoryStatus(StrEnum):
    """Whether accumulated opening amortization has been explicitly established."""

    KNOWN = "known"
    MISSING = "missing"


class AcquisitionLineageReference(BaseModel):
    """Canonical transaction evidence observed by one immutable asset revision."""

    model_config = STRICT_FROZEN_CONFIG

    observed_transaction_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_lineage_event_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    invoice_evidence_id: str = Field(min_length=1, max_length=256)
    evidence_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    def resolve_current_transaction_id(self, replacements: dict[str, str]) -> str:
        """Follow a supplied canonical edit-lineage map without minting an ID.

        The application ledger owns construction of ``replacements``.  Keeping
        this narrow domain operation pure preserves the observed ID on the
        revision while enabling stale-state detection after ID-affecting edits.
        """
        current = self.observed_transaction_id
        seen: set[str] = set()
        while current in replacements:
            if current in seen:
                raise ActividadAssetValidationError("transaction edit lineage contains a cycle")
            seen.add(current)
            current = replacements[current]
        return current


class OpeningAmortizationHistory(BaseModel):
    """Recorded pre-onboarding amortization, deliberately distinct from zero."""

    model_config = STRICT_FROZEN_CONFIG

    status: OpeningHistoryStatus
    accumulated_amount: Decimal | None = None

    @field_validator("accumulated_amount")
    @classmethod
    def _require_finite_nonnegative_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or value < Decimal("0")):
            raise ValueError("accumulated_amount must be a finite non-negative Decimal")
        return value

    @model_validator(mode="after")
    def _validate_status_shape(self) -> Self:
        if self.status is OpeningHistoryStatus.KNOWN and self.accumulated_amount is None:
            raise ValueError("known opening history requires accumulated_amount")
        if self.status is OpeningHistoryStatus.MISSING and self.accumulated_amount is not None:
            raise ValueError("missing opening history cannot declare accumulated_amount")
        return self


class AssetBasisStage(StrEnum):
    """The point at which an acquisition cost has already been allocated."""

    WHOLE_PROPERTY = "whole_property"
    TAXPAYER_OWNED = "taxpayer_owned"
    BUSINESS_ALLOCATED = "business_allocated"


class ActivityAssetBasis(BaseModel):
    """Typed cost basis that applies each allocation fact at most once.

    A whole-property basis is the only mixed-use property shape and applies
    direct ownership and property-area use here.  A taxpayer-owned basis
    declares that ownership has already been resolved and applies one
    ordinary-asset business-use share.  A business-allocated basis is the
    final amount, names the prior allocation source, and accepts no further
    percentage facts.
    """

    model_config = STRICT_FROZEN_CONFIG

    stage: AssetBasisStage
    basis_amount: Decimal
    is_property: bool = False
    construction_cost: Decimal | None = None
    land_cost: Decimal | None = None
    ownership_mode: OwnershipMode | None = None
    ownership_share: Decimal | None = None
    office_area: Decimal | None = None
    total_area: Decimal | None = None
    business_use_share: Decimal | None = None
    prior_allocation_provenance: str | None = Field(default=None, min_length=1, max_length=512)

    @field_validator(
        "basis_amount",
        "construction_cost",
        "land_cost",
        "office_area",
        "total_area",
        "ownership_share",
        "business_use_share",
    )
    @classmethod
    def _require_finite_nonnegative(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or value < Decimal("0")):
            raise ValueError("allocation amounts must be finite non-negative Decimals")
        return value

    @model_validator(mode="after")
    def _validate_basis_shape(self) -> Self:
        if self.basis_amount <= Decimal("0"):
            raise ValueError("basis_amount must be positive")
        if self.stage is AssetBasisStage.WHOLE_PROPERTY:
            self._require_whole_property_facts()
        elif self.stage is AssetBasisStage.TAXPAYER_OWNED:
            self._require_taxpayer_owned_facts()
        else:
            self._require_business_allocated_facts()
        return self

    def _require_whole_property_facts(self) -> None:
        if not self.is_property:
            raise ValueError("whole-property basis is only valid for property")
        self._require_property_components()
        if self.ownership_mode is None:
            raise ValueError("whole-property basis requires ownership_mode")
        if self.business_use_share is not None:
            raise ValueError("whole-property property basis uses office area, not business_use_share")
        if self.prior_allocation_provenance is not None:
            raise ValueError("whole-property basis cannot declare prior allocation provenance")
        self._validate_direct_ownership()

    def _require_taxpayer_owned_facts(self) -> None:
        if self.ownership_mode is not None or self.ownership_share is not None:
            raise ValueError("taxpayer-owned basis cannot apply ownership a second time")
        if self.is_property:
            raise ValueError("mixed-use property must declare a whole-property basis")
        if self.prior_allocation_provenance is not None:
            raise ValueError("taxpayer-owned basis cannot declare prior allocation provenance")
        ordinary_asset_property_facts = (
            self.construction_cost,
            self.land_cost,
            self.office_area,
            self.total_area,
        )
        if any(value is not None for value in ordinary_asset_property_facts):
            raise ValueError("construction, land, and office-area facts are only valid for property")
        self._require_share(self.business_use_share, "taxpayer-owned ordinary asset requires business_use_share")

    def _require_business_allocated_facts(self) -> None:
        if self.is_property:
            raise ValueError("mixed-use property must declare a whole-property basis")
        if self.prior_allocation_provenance is None:
            raise ValueError("business-allocated basis requires prior_allocation_provenance")
        if any(
            value is not None
            for value in (
                self.construction_cost,
                self.land_cost,
                self.ownership_mode,
                self.ownership_share,
                self.office_area,
                self.total_area,
                self.business_use_share,
            )
        ):
            raise ValueError("business-allocated basis cannot apply allocation facts again")

    def _require_property_components(self) -> None:
        if (
            self.construction_cost is None
            or self.land_cost is None
            or self.office_area is None
            or self.total_area is None
        ):
            raise ValueError("property basis requires construction, land, office_area, and total_area")
        if self.construction_cost <= Decimal("0") or self.construction_cost + self.land_cost != self.basis_amount:
            raise ValueError("property construction_cost plus land_cost must equal basis_amount")
        if self.office_area <= Decimal("0") or self.total_area <= Decimal("0") or self.office_area > self.total_area:
            raise ValueError("property office_area must be positive and no greater than total_area")

    def _validate_direct_ownership(self) -> None:
        if self.ownership_mode is OwnershipMode.SPOUSAL_COMMUNITY:
            raise ActividadAssetUnsupportedError(
                "spousal community ownership is not enrolled for activity-asset allocation",
            )
        if self.ownership_mode is OwnershipMode.SOLE:
            if self.ownership_share != Decimal("1"):
                raise ValueError("sole ownership requires ownership_share of exactly one")
            return
        if self.ownership_mode is OwnershipMode.FRACTIONAL_DIRECT:
            self._require_share(self.ownership_share, "fractional direct ownership requires ownership_share")
            if self.ownership_share == Decimal("1"):
                raise ValueError("fractional direct ownership_share must be below one")
            return
        raise ActividadAssetValidationError("whole-property basis has an unknown ownership treatment")

    @staticmethod
    def _require_share(value: Decimal | None, message: str) -> None:
        if value is None or not Decimal("0") < value <= Decimal("1"):
            raise ValueError(message)

    def deductible_basis(self) -> Decimal:
        """Return final depreciation basis without reapplying any allocation fact."""
        if self.stage is AssetBasisStage.BUSINESS_ALLOCATED:
            return self.basis_amount
        if self.stage is AssetBasisStage.TAXPAYER_OWNED:
            if self.business_use_share is None:  # defensive: validator proves unreachable
                raise ActividadAssetValidationError("ordinary asset lacks business_use_share")
            return self.basis_amount * self.business_use_share
        if (
            self.construction_cost is None
            or self.ownership_share is None
            or self.office_area is None
            or self.total_area is None
        ):
            raise ActividadAssetValidationError("whole-property basis lacks allocation components")
        return self.construction_cost * self.ownership_share * self.office_area / self.total_area


class ActivityAssetRevision(BaseModel):
    """One immutable revision of an independently identified activity asset."""

    model_config = STRICT_FROZEN_CONFIG

    asset_id: str = Field(min_length=1, max_length=128)
    revision_number: int = Field(ge=1)
    supersedes_revision_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    acquisition: AcquisitionLineageReference
    acquisition_shape: AcquisitionShape
    asset_kind: AssetKind
    basis: ActivityAssetBasis
    residual_value: Decimal = Decimal("0")
    in_service_date: date
    out_of_service_date: date | None = None
    opening_history: OpeningAmortizationHistory
    acquired_condition: AcquiredCondition
    building_construction_date: date | None = None
    amortization: ActivityAssetAmortizationElection

    @field_validator("asset_id")
    @classmethod
    def _trim_asset_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("asset_id must not be blank")
        return normalized

    @field_validator("residual_value")
    @classmethod
    def _require_valid_residual(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < Decimal("0"):
            raise ValueError("residual_value must be a finite non-negative Decimal")
        return value

    @model_validator(mode="after")
    def _validate_revision_shape(self) -> Self:
        if self.revision_number == 1 and self.supersedes_revision_id is not None:
            raise ValueError("first asset revision cannot supersede another revision")
        if self.revision_number > 1 and self.supersedes_revision_id is None:
            raise ValueError("later asset revisions require supersedes_revision_id")
        if self.acquisition_shape is not AcquisitionShape.PRIMARY_PURCHASE:
            raise ValueError("initial activity-asset support requires one primary purchase transaction")
        if self.out_of_service_date is not None and self.out_of_service_date <= self.in_service_date:
            raise ValueError("out_of_service_date must be after in_service_date")
        if self.residual_value >= self.basis.deductible_basis():
            raise ValueError("residual_value must be below allocated depreciation basis")
        if self.building_construction_date is not None:
            if self.acquired_condition is not AcquiredCondition.USED:
                raise ValueError("building_construction_date is only a fact of a used asset")
            if self.building_construction_date > self.in_service_date:
                raise ValueError("building_construction_date cannot follow in_service_date")
        return self

    def amortizable_basis(self) -> Decimal:
        """Return the allocated basis less residual value (RIS art. 3.2)."""
        return self.basis.deductible_basis() - self.residual_value

    @property
    def revision_id(self) -> str:
        """Return the deterministic identity of this immutable revision."""
        payload = self.model_dump(mode="json", exclude={"supersedes_revision_id"})
        payload["supersedes_revision_id"] = self.supersedes_revision_id
        return content_hash_hex(payload)

    def is_stale_for(self, replacements: dict[str, str]) -> bool:
        """Return whether canonical lineage now resolves beyond the observed transaction ID."""
        return self.acquisition.resolve_current_transaction_id(replacements) != self.acquisition.observed_transaction_id


__all__ = [
    "AcquisitionLineageReference",
    "AcquisitionShape",
    "ActivityAssetBasis",
    "ActivityAssetRevision",
    "AssetBasisStage",
    "AssetKind",
    "OpeningAmortizationHistory",
    "OpeningHistoryStatus",
    "OwnershipMode",
]
