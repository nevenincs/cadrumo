"""Immutable IRPF activity-asset facts and acquisition lineage."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from enum import StrEnum
from functools import cached_property
from typing import Annotated, Final, Protocol, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.filing_year import FilingYear
from ....core.hashing import content_hash_hex
from ....core.hex import Hex64Str
from ....core.identity.transaction_ids import TransactionId
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.money.rounding import round_to_cents
from ....core.tipos_actividad import TipoActividad
from .disposal import ActivityAssetDisposal
from .election import AcquiredCondition, ActivityAssetAmortizationElection, AmortizationMethod
from .errors import ActividadAssetUnsupportedError, ActividadAssetValidationError
from .fact_leaves import Internal, Share
from .identity_cache import CachedIdentityModel
from .vehicle_affectation import VehicleAffectation


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
    FINANCIAL_LEASE_UNEXERCISED = "financial_lease_unexercised"
    ACQUIRED_OUTSIDE_LEDGER = "acquired_outside_ledger"


REGISTERABLE_ACQUISITION_SHAPES: Final[tuple[AcquisitionShape, ...]] = (
    AcquisitionShape.PRIMARY_PURCHASE,
    AcquisitionShape.ACQUIRED_OUTSIDE_LEDGER,
)
"""The shapes an element can be registered under, which is all a form may offer."""

FURTHER_ACQUISITION_SHAPES: Final[tuple[AcquisitionShape, ...]] = (
    AcquisitionShape.SPLIT_PAYMENT,
    AcquisitionShape.ANCILLARY_COST,
)
"""The shapes a later ledger row of an element's acquisition can take, which a registered element names."""


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
    """The evidence one immutable asset revision observed for its acquisition.

    An element acquired outside the ledger has no row and no fingerprint; its
    ``invoice_evidence_id`` is the reference to the document the filer holds.
    """

    model_config = STRICT_FROZEN_CONFIG

    observed_transaction_id: Annotated[TransactionId | None, Internal] = None
    observed_lineage_event_id: Annotated[Hex64Str | None, Internal] = None
    invoice_evidence_id: str = Field(max_length=256)
    evidence_fingerprint: Annotated[Hex64Str | None, Internal] = None


class FurtherAcquisitionRow(BaseModel):
    """One more ledger row of an element's acquisition: a later instalment or an ancillary cost.

    The row reconciles against the register's basis and deducts nothing itself.
    """

    model_config = STRICT_FROZEN_CONFIG

    shape: AcquisitionShape
    lineage: AcquisitionLineageReference

    @model_validator(mode="after")
    def _require_a_further_shape(self) -> Self:
        if self.shape not in FURTHER_ACQUISITION_SHAPES:
            raise ValueError("a further acquisition row is a split payment or an ancillary cost")
        if self.lineage.observed_transaction_id is None:
            raise ValueError("a further acquisition row names a ledger row")
        return self


class OpeningAmortizationHistory(BaseModel):
    """Recorded pre-onboarding amortization, deliberately distinct from zero."""

    model_config = STRICT_FROZEN_CONFIG

    status: OpeningHistoryStatus
    accumulated_amount: Decimal | None = None
    amortization_method: AmortizationMethod | None = None
    """The method under which the opening amount was charged, when attested."""
    covered_through_tax_year: FilingYear | None = None
    """The last tax year the opening amount covers; a non-zero known amount requires it."""

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
        if self.status is OpeningHistoryStatus.MISSING and (
            self.accumulated_amount is not None or self.amortization_method is not None
        ):
            raise ValueError("missing opening history cannot declare an amount or its method")
        has_amount = bool(self.accumulated_amount)
        if has_amount and self.covered_through_tax_year is None:
            raise ValueError("a non-zero opening amount requires covered_through_tax_year")
        if not has_amount and self.covered_through_tax_year is not None:
            raise ValueError("covered_through_tax_year is only a fact of a non-zero opening amount")
        return self


class AssetBasisStage(StrEnum):
    """The point at which an acquisition cost has already been allocated."""

    WHOLE_PROPERTY = "whole_property"
    TAXPAYER_OWNED = "taxpayer_owned"
    BUSINESS_ALLOCATED = "business_allocated"


BASIS_STAGE_FACTS: Mapping[AssetBasisStage, tuple[str, ...]] = {
    AssetBasisStage.WHOLE_PROPERTY: (
        "construction_cost",
        "land_cost",
        "ownership_mode",
        "ownership_share",
        "office_area",
        "total_area",
    ),
    AssetBasisStage.TAXPAYER_OWNED: ("business_use_share",),
    AssetBasisStage.BUSINESS_ALLOCATED: ("prior_allocation_provenance",),
}
"""The facts of a basis, beyond its amounts, that each stage states and no other stage may."""

OPENING_STATUS_FACTS: Mapping[OpeningHistoryStatus, tuple[str, ...]] = {
    OpeningHistoryStatus.KNOWN: ("accumulated_amount", "amortization_method", "covered_through_tax_year"),
    OpeningHistoryStatus.MISSING: (),
}
"""The facts of an opening history that each status can state; a missing history states none."""


class ActivityAssetBasis(BaseModel):
    """Typed cost basis that applies each allocation fact at most once.

    A whole-property basis is the only mixed-use property shape and applies
    direct ownership and property-area use here.  A taxpayer-owned basis
    declares that ownership has already been resolved and applies one
    ordinary-asset business-use share.  A business-allocated basis is the
    final amount, names the prior allocation source, and accepts no further
    percentage facts.

    The amortizable cost is the price plus the IVA the taxpayer cannot deduct
    at acquisition.  ``basis_amount`` is the
    price alone and ``non_deductible_iva`` is that IVA, stated explicitly even
    when it is zero.  The IVA joins the cost once, before the stage's
    allocation fact applies, so it follows the same share as the price.  In a
    whole-property basis it joins the construction cost, because land is not
    amortized and the IVA of the sale attaches to the building.  A later
    regularization of deducted IVA (LIVA arts. 107 to 110) has no field here
    and changes neither the basis nor the schedule.
    """

    model_config = STRICT_FROZEN_CONFIG

    stage: AssetBasisStage
    basis_amount: Decimal
    non_deductible_iva: Decimal
    is_property: bool = False
    construction_cost: Decimal | None = None
    land_cost: Decimal | None = None
    ownership_mode: OwnershipMode | None = None
    ownership_share: Share | None = None
    office_area: Decimal | None = None
    total_area: Decimal | None = None
    business_use_share: Share | None = None
    prior_allocation_provenance: str | None = Field(default=None, min_length=1, max_length=512)

    @field_validator(
        "basis_amount",
        "non_deductible_iva",
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
    @pydantic_validation_boundary
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
                translated_message="ledger.actividad_asset.errors.spousal_community_ownership_unsupported"
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
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.ownership_treatment_unknown"
        )

    @staticmethod
    def _require_share(value: Decimal | None, message: str) -> None:
        if value is None or not Decimal("0") < value <= Decimal("1"):
            raise ValueError(message)

    def acquisition_cost(self) -> Decimal:
        """Return the price plus non-deductible IVA, before any allocation fact.

        This is the precio de adquisicion of the element: the value the
        EUR 300 test of LIS art. 12.3.e compares, and the amount the stage's
        allocation fact then reduces to the deductible basis.
        """
        return self.basis_amount + self.non_deductible_iva

    def allocation_share(self) -> Decimal:
        """Return the share of the whole element that this taxpayer's activity holds.

        A business-allocated cost is already that share, so nothing reduces it again.
        """
        if self.stage is AssetBasisStage.BUSINESS_ALLOCATED:
            return Decimal("1")
        if self.stage is AssetBasisStage.TAXPAYER_OWNED:
            if self.business_use_share is None:  # defensive: validator proves unreachable
                raise ActividadAssetValidationError(
                    translated_message="ledger.actividad_asset.errors.business_use_share_missing"
                )
            return self.business_use_share
        if self.ownership_share is None or self.office_area is None or self.total_area is None:
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.allocation_components_missing"
            )
        return self.ownership_share * self.office_area / self.total_area

    def allocated_acquisition_value(self) -> Decimal:
        """Return the allocated price plus non-deductible IVA, keeping the land the basis leaves out."""
        return self.acquisition_cost() * self.allocation_share()

    def deductible_basis(self) -> Decimal:
        """Return final depreciation basis without reapplying any allocation fact."""
        if self.stage is AssetBasisStage.BUSINESS_ALLOCATED:
            return self.acquisition_cost()
        if self.stage is AssetBasisStage.TAXPAYER_OWNED:
            if self.business_use_share is None:  # defensive: validator proves unreachable
                raise ActividadAssetValidationError(
                    translated_message="ledger.actividad_asset.errors.business_use_share_missing"
                )
            return self.acquisition_cost() * self.business_use_share
        if (
            self.construction_cost is None
            or self.ownership_share is None
            or self.office_area is None
            or self.total_area is None
        ):
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.allocation_components_missing"
            )
        building_cost = self.construction_cost + self.non_deductible_iva
        return building_cost * self.ownership_share * self.office_area / self.total_area


_FIGURE_NEUTRAL_FIELDS: set[str] = {
    "revision_number",
    "supersedes_revision_id",
    "out_of_service_date",
    "disposal",
    "acquisition",
    "acquisition_shape",
    "further_acquisitions",
    "declared_acquisition_date",
    "declared_activity",
}
"""What a revision states without any charge resting on it.

A revision's place in its chain and its baja leave every earlier charge's facts unchanged.  The
acquisition's evidence and rows reconcile against the stated basis and deduct nothing, and the
declared date and activity place the element on a return without moving a claim's figure.
"""


class _ActivityDeclaringRow(Protocol):
    """What the activity of an element is read from on its acquisition row."""

    @property
    def tipo_actividad(self) -> TipoActividad | None:
        """The activity the row declares, if any."""
        ...


class ActivityAssetRevision(CachedIdentityModel):
    """One immutable revision of an independently identified activity asset."""

    model_config = STRICT_FROZEN_CONFIG

    asset_id: Annotated[str, Internal] = Field(min_length=1, max_length=128)
    revision_number: Annotated[int, Internal] = Field(ge=1)
    supersedes_revision_id: Annotated[Hex64Str | None, Internal] = None
    acquisition: AcquisitionLineageReference
    acquisition_shape: AcquisitionShape
    further_acquisitions: tuple[FurtherAcquisitionRow, ...] = ()
    declared_acquisition_date: date | None = None
    """When an element acquired outside the ledger was acquired; a ledger row states its own date."""
    declared_activity: TipoActividad | None = None
    """The activity of an element acquired outside the ledger; a ledger row states its own."""
    asset_kind: AssetKind
    basis: ActivityAssetBasis
    residual_value: Decimal = Decimal("0")
    in_service_date: date
    out_of_service_date: date | None = None
    """The exclusive end of the charge window, which only a baja states."""
    disposal: ActivityAssetDisposal | None = None
    opening_history: OpeningAmortizationHistory
    acquired_condition: AcquiredCondition
    building_construction_date: date | None = None
    amortization: ActivityAssetAmortizationElection
    vehicle_affectation: VehicleAffectation | None = None

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
    @pydantic_validation_boundary
    def _validate_revision_shape(self) -> Self:
        from .revision_validation import validate_revision

        validate_revision(self)
        return self

    def amortizable_basis(self) -> Decimal:
        """Return the allocated basis less residual value (RIS art. 3.2)."""
        return self.basis.deductible_basis() - self.residual_value

    def amortizable_ceiling(self) -> Decimal:
        """Return the most that charges, each emitted in cents, can lawfully add up to."""
        return round_to_cents(self.amortizable_basis())

    @property
    def acquisition_transaction_ids(self) -> tuple[TransactionId, ...]:
        """Return every ledger row this revision owns as its acquisition, the primary one first; possibly none."""
        return tuple(
            transaction_id
            for transaction_id in (
                self.acquisition.observed_transaction_id,
                *(row.lineage.observed_transaction_id for row in self.further_acquisitions),
            )
            if transaction_id is not None
        )

    def acquisition_row_in[RowT](self, rows: Mapping[str, RowT]) -> RowT | None:
        """Return the primary acquisition row from ``rows``; an element outside the ledger has none."""
        transaction_id = self.acquisition.observed_transaction_id
        return None if transaction_id is None else rows.get(transaction_id)

    def activity_in(self, rows: Mapping[str, _ActivityDeclaringRow]) -> TipoActividad | None:
        """Return the activity this element belongs to, stated on it or on its acquisition row in ``rows``."""
        if self.declared_activity is not None:
            return self.declared_activity
        row = self.acquisition_row_in(rows)
        return None if row is None else row.tipo_actividad

    @cached_property
    def revision_id(self) -> str:
        """Return the deterministic identity of this immutable revision.

        A revision with no baja, further acquisition row, declared acquisition date or declared
        activity omits that field, so its identity is unchanged by it.
        """
        excluded = {"supersedes_revision_id"}
        if self.disposal is None:
            excluded.add("disposal")
        if not self.further_acquisitions:
            excluded.add("further_acquisitions")
        if self.declared_acquisition_date is None:
            excluded.add("declared_acquisition_date")
        if self.declared_activity is None:
            excluded.add("declared_activity")
        payload = self.model_dump(mode="json", exclude=excluded)
        payload["supersedes_revision_id"] = self.supersedes_revision_id
        return content_hash_hex(payload)

    def same_charge_facts(self, other: ActivityAssetRevision) -> bool:
        """Say whether two revisions state every fact a charge rests on, whatever else each records."""
        return self.model_dump(exclude=_FIGURE_NEUTRAL_FIELDS) == other.model_dump(exclude=_FIGURE_NEUTRAL_FIELDS)

    def with_disposal(self, disposal: ActivityAssetDisposal) -> ActivityAssetRevision:
        """Return the superseding revision recording a baja, every other fact copied unchanged."""
        if disposal.disposal_date < self.in_service_date:
            raise ActividadAssetValidationError(
                context={
                    "disposal_date": disposal.disposal_date,
                    "in_service_date": self.in_service_date,
                },
                translated_message="ledger.actividad_asset.errors.disposal_before_service",
            )
        from .revision_validation import require_later_affectation_in_order

        require_later_affectation_in_order(self, disposal)
        facts = {name: getattr(self, name) for name in type(self).model_fields}
        facts.update(
            revision_number=self.revision_number + 1,
            supersedes_revision_id=self.revision_id,
            out_of_service_date=disposal.boundary,
            disposal=disposal,
        )
        return ActivityAssetRevision(**facts)


__all__ = [
    "BASIS_STAGE_FACTS",
    "FURTHER_ACQUISITION_SHAPES",
    "OPENING_STATUS_FACTS",
    "REGISTERABLE_ACQUISITION_SHAPES",
    "AcquisitionLineageReference",
    "AcquisitionShape",
    "ActivityAssetBasis",
    "ActivityAssetRevision",
    "AssetBasisStage",
    "AssetKind",
    "FurtherAcquisitionRow",
    "OpeningAmortizationHistory",
    "OpeningHistoryStatus",
    "OwnershipMode",
]
