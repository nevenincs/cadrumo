"""Closed operation wire snapshots for activity-asset financial facts.

These DTOs are the stable registered-operation boundary.  Decimal facts cross
that boundary only as :class:`PublicDecimal`; existing domain records remain
the private canonical representation used by services and encrypted storage.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final, Self

from pydantic import BaseModel, Field, ValidationError, model_validator

from ...application.operations.public_scalar import PublicDecimal, project_scalar
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.hex import Hex64Str
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.renta.actividad_asset.claims import AmortizationClaim, ClaimProjection
from ...domain.renta.actividad_asset.disposal import (
    ActivityAssetDisposal,
    ActivityAssetDisposalReason,
    PriorFreeDepreciationRegime,
    require_admissible_disposal,
)
from ...domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    ApprovedAmortizationPlan,
    ChargingInfrastructureEvidence,
    DefiniteUsefulLife,
    DigitOrder,
    DirectEstimationRegime,
    ElectionReference,
    EvidenceReference,
    LowValueElection,
    PlanAnnualAmount,
    PlanApprovalKind,
    RenewableSelfConsumptionEvidence,
    SmallEnterpriseEvidence,
)
from ...domain.renta.actividad_asset.errors import ActividadAssetValidationError
from ...domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
    OwnershipMode,
)
from ...domain.renta.actividad_asset.register_records import ActivityAssetDescriptor, ActivityAssetHistoryEvent
from ...domain.renta.actividad_asset.schedule import ScheduledAmortizationCharge
from ...domain.renta.actividad_asset.vehicle_affectation import VehicleAffectation
from .activity_asset_read_models import ActivityAssetM130Contribution, ActivityAssetM130ProjectionSnapshot
from .history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from .operations import ActivityAssetFilingHandoff, M130AccrualProjection, M130Contribution


def _decimal(value: PublicDecimal | None) -> Decimal | None:
    return None if value is None else Decimal(value.decimal)


_CHARGE_DECIMAL_FIELDS: Final = (
    "amount",
    "annual_rate",
    "free_depreciation_unit_acquisition_value",
    "free_depreciation_annual_cap",
)
"""Decimal facts of a scheduled charge or a recorded claim; only a forecast states its rate."""


def _public_charge_fields(value: BaseModel) -> dict[str, object]:
    """Copy a domain charge field by field, carrying its decimals as public decimals."""
    data: dict[str, object] = {}
    data.update(value.model_dump(mode="python"))
    for name in _CHARGE_DECIMAL_FIELDS:
        if name in data:
            amount = data[name]
            data[name] = PublicDecimal(decimal=str(amount)) if amount is not None else None
    return data


def _domain_charge_fields(snapshot: BaseModel) -> dict[str, object]:
    """Copy a charge snapshot field by field, restoring its public decimals."""
    data: dict[str, object] = {name: getattr(snapshot, name) for name in type(snapshot).model_fields}
    for name in _CHARGE_DECIMAL_FIELDS:
        if name in data:
            amount = data[name]
            if amount is not None and not isinstance(amount, PublicDecimal):
                raise TypeError("charge decimal must be a public decimal")
            data[name] = _decimal(amount)
    return data


class AcquisitionLineageSnapshot(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    observed_transaction_id: TransactionId
    observed_lineage_event_id: Hex64Str | None = None
    invoice_evidence_id: str = Field(min_length=1, max_length=256)
    evidence_fingerprint: Hex64Str

    @classmethod
    def from_domain(cls, value: AcquisitionLineageReference) -> Self:
        return cls(**value.model_dump(mode="python"))

    def to_domain(self) -> AcquisitionLineageReference:
        return AcquisitionLineageReference(**self.model_dump(mode="python"))


class OpeningHistorySnapshot(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    status: OpeningHistoryStatus
    accumulated_amount: PublicDecimal | None = None
    amortization_method: AmortizationMethod | None = None
    covered_through_tax_year: FilingYear | None = None

    @classmethod
    def from_domain(cls, value: OpeningAmortizationHistory) -> Self:
        return cls(
            status=value.status,
            accumulated_amount=(
                project_scalar(value.accumulated_amount) if value.accumulated_amount is not None else None
            ),
            amortization_method=value.amortization_method,
            covered_through_tax_year=value.covered_through_tax_year,
        )

    def to_domain(self) -> OpeningAmortizationHistory:
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


class PlanAnnualAmountSnapshot(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    tax_year: FilingYear
    amount: PublicDecimal

    @classmethod
    def from_domain(cls, value: PlanAnnualAmount) -> Self:
        return cls(tax_year=value.tax_year, amount=project_scalar(value.amount))

    def to_domain(self) -> PlanAnnualAmount:
        return PlanAnnualAmount(tax_year=self.tax_year, amount=Decimal(self.amount.decimal))


class ApprovedAmortizationPlanSnapshot(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    approval_reference: ElectionReference
    approval_kind: PlanApprovalKind
    submitted_on: date
    resolved_on: date
    annual_amounts: tuple[PlanAnnualAmountSnapshot, ...] = Field(min_length=1)

    @classmethod
    def from_domain(cls, value: ApprovedAmortizationPlan) -> Self:
        return cls(
            approval_reference=value.approval_reference,
            approval_kind=value.approval_kind,
            submitted_on=value.submitted_on,
            resolved_on=value.resolved_on,
            annual_amounts=tuple(PlanAnnualAmountSnapshot.from_domain(item) for item in value.annual_amounts),
        )

    def to_domain(self) -> ApprovedAmortizationPlan:
        return ApprovedAmortizationPlan(
            approval_reference=self.approval_reference,
            approval_kind=self.approval_kind,
            submitted_on=self.submitted_on,
            resolved_on=self.resolved_on,
            annual_amounts=tuple(item.to_domain() for item in self.annual_amounts),
        )


class SmallEnterpriseEvidenceSnapshot(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    evidence_reference: EvidenceReference
    made_available_on: date
    prior_period_net_turnover: PublicDecimal

    @classmethod
    def from_domain(cls, value: SmallEnterpriseEvidence) -> Self:
        return cls(
            evidence_reference=value.evidence_reference,
            made_available_on=value.made_available_on,
            prior_period_net_turnover=project_scalar(value.prior_period_net_turnover),
        )

    def to_domain(self) -> SmallEnterpriseEvidence:
        return SmallEnterpriseEvidence(
            evidence_reference=self.evidence_reference,
            made_available_on=self.made_available_on,
            prior_period_net_turnover=Decimal(self.prior_period_net_turnover.decimal),
        )


class LowValueElectionSnapshot(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    election_reference: ElectionReference
    new_material_evidence_reference: EvidenceReference

    @classmethod
    def from_domain(cls, value: LowValueElection) -> Self:
        return cls(
            election_reference=value.election_reference,
            new_material_evidence_reference=value.new_material_evidence_reference,
        )

    def to_domain(self) -> LowValueElection:
        return LowValueElection(
            election_reference=self.election_reference,
            new_material_evidence_reference=self.new_material_evidence_reference,
        )


class ActivityAssetAmortizationElectionSnapshot(BaseModel):
    """Public election DTO with explicit decimals in every nested fact."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    regime: DirectEstimationRegime
    method: AmortizationMethod
    authority_class_key: str | None = Field(default=None, min_length=1, max_length=64)
    linear_coefficient: PublicDecimal | None = None
    shift_hours_per_day: PublicDecimal | None = None
    sum_of_digits_period_years: int | None = Field(default=None, ge=1, le=100)
    digit_order: DigitOrder | None = None
    approved_plan: ApprovedAmortizationPlanSnapshot | None = None
    useful_life: DefiniteUsefulLife | None = None
    small_enterprise: SmallEnterpriseEvidenceSnapshot | None = None
    low_value: LowValueElectionSnapshot | None = None
    research_development_evidence_reference: EvidenceReference | None = None
    charging_infrastructure: ChargingInfrastructureEvidence | None = None
    renewable_self_consumption: RenewableSelfConsumptionEvidence | None = None

    @classmethod
    def from_domain(cls, value: ActivityAssetAmortizationElection) -> Self:
        """Project a canonical election into its bounded wire form."""
        return cls(
            regime=value.regime,
            method=value.method,
            authority_class_key=value.authority_class_key,
            linear_coefficient=(
                project_scalar(value.linear_coefficient) if value.linear_coefficient is not None else None
            ),
            shift_hours_per_day=(
                project_scalar(value.shift_hours_per_day) if value.shift_hours_per_day is not None else None
            ),
            sum_of_digits_period_years=value.sum_of_digits_period_years,
            digit_order=value.digit_order,
            approved_plan=(
                ApprovedAmortizationPlanSnapshot.from_domain(value.approved_plan)
                if value.approved_plan is not None
                else None
            ),
            useful_life=value.useful_life,
            small_enterprise=(
                SmallEnterpriseEvidenceSnapshot.from_domain(value.small_enterprise)
                if value.small_enterprise is not None
                else None
            ),
            low_value=(LowValueElectionSnapshot.from_domain(value.low_value) if value.low_value is not None else None),
            research_development_evidence_reference=value.research_development_evidence_reference,
            charging_infrastructure=value.charging_infrastructure,
            renewable_self_consumption=value.renewable_self_consumption,
        )

    def to_domain(self) -> ActivityAssetAmortizationElection:
        """Restore the canonical election and its nested evidence."""
        return ActivityAssetAmortizationElection(
            regime=self.regime,
            method=self.method,
            authority_class_key=self.authority_class_key,
            linear_coefficient=_decimal(self.linear_coefficient),
            shift_hours_per_day=_decimal(self.shift_hours_per_day),
            sum_of_digits_period_years=self.sum_of_digits_period_years,
            digit_order=self.digit_order,
            approved_plan=self.approved_plan.to_domain() if self.approved_plan is not None else None,
            useful_life=self.useful_life,
            small_enterprise=self.small_enterprise.to_domain() if self.small_enterprise is not None else None,
            low_value=self.low_value.to_domain() if self.low_value is not None else None,
            research_development_evidence_reference=self.research_development_evidence_reference,
            charging_infrastructure=self.charging_infrastructure,
            renewable_self_consumption=self.renewable_self_consumption,
        )

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _canonical(self) -> Self:
        self.to_domain()
        return self


class ActivityAssetDisposalSnapshot(BaseModel):
    """Public baja statement; its reason and amount rules are judged when it becomes the record.

    A request carries this unjudged so that a refused reason reaches the operator as
    its registered refusal and not as a malformed request.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    disposal_date: date
    reason: ActivityAssetDisposalReason
    proceeds: PublicDecimal
    transmission_costs: PublicDecimal
    market_value: PublicDecimal | None = None
    prior_free_depreciation_regime: PriorFreeDepreciationRegime | None = None
    later_affectation_on: date | None = None

    @classmethod
    def from_domain(cls, value: ActivityAssetDisposal) -> Self:
        """Project one baja record without changing its facts."""
        return cls(
            disposal_date=value.disposal_date,
            reason=value.reason,
            proceeds=project_scalar(value.proceeds),
            transmission_costs=project_scalar(value.transmission_costs),
            market_value=None if value.market_value is None else project_scalar(value.market_value),
            prior_free_depreciation_regime=value.prior_free_depreciation_regime,
            later_affectation_on=value.later_affectation_on,
        )

    def to_domain(self) -> ActivityAssetDisposal:
        """Judge the statement and restore the canonical record.

        Raises:
            ActividadAssetValidationError: When the reason cannot carry these amounts
                or an amount is not a non-negative figure in euro cents.
            ActividadAssetUnsupportedError: When the reason is a donation.
        """
        proceeds = Decimal(self.proceeds.decimal)
        costs = Decimal(self.transmission_costs.decimal)
        market_value = _decimal(self.market_value)
        require_admissible_disposal(
            self.reason,
            proceeds=proceeds,
            transmission_costs=costs,
            market_value=market_value,
        )
        try:
            return ActivityAssetDisposal(
                disposal_date=self.disposal_date,
                reason=self.reason,
                proceeds=proceeds,
                transmission_costs=costs,
                market_value=market_value,
                prior_free_depreciation_regime=self.prior_free_depreciation_regime,
                later_affectation_on=self.later_affectation_on,
            )
        except ValidationError as error:
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.disposal_amount_invalid",
            ) from error


class ActivityAssetRevisionSnapshot(BaseModel):
    """Public revision DTO with all monetary and fractional facts explicit."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    asset_id: str = Field(min_length=1, max_length=128)
    revision_number: int = Field(ge=1)
    supersedes_revision_id: Hex64Str | None = None
    acquisition: AcquisitionLineageSnapshot
    acquisition_shape: AcquisitionShape
    asset_kind: AssetKind
    basis: ActivityAssetBasisSnapshot
    residual_value: PublicDecimal = Field(default_factory=lambda: PublicDecimal(decimal="0"))
    in_service_date: date
    out_of_service_date: date | None = None
    disposal: ActivityAssetDisposalSnapshot | None = None
    opening_history: OpeningHistorySnapshot
    acquired_condition: AcquiredCondition
    building_construction_date: date | None = None
    amortization: ActivityAssetAmortizationElectionSnapshot
    vehicle_affectation: VehicleAffectation | None = None

    @classmethod
    def from_domain(cls, value: ActivityAssetRevision) -> Self:
        """Project one immutable revision without changing its facts."""
        return cls(
            asset_id=value.asset_id,
            revision_number=value.revision_number,
            supersedes_revision_id=value.supersedes_revision_id,
            acquisition=AcquisitionLineageSnapshot.from_domain(value.acquisition),
            acquisition_shape=value.acquisition_shape,
            asset_kind=value.asset_kind,
            basis=ActivityAssetBasisSnapshot.from_domain(value.basis),
            residual_value=project_scalar(value.residual_value),
            in_service_date=value.in_service_date,
            out_of_service_date=value.out_of_service_date,
            disposal=None if value.disposal is None else ActivityAssetDisposalSnapshot.from_domain(value.disposal),
            opening_history=OpeningHistorySnapshot.from_domain(value.opening_history),
            acquired_condition=value.acquired_condition,
            building_construction_date=value.building_construction_date,
            amortization=ActivityAssetAmortizationElectionSnapshot.from_domain(value.amortization),
            vehicle_affectation=value.vehicle_affectation,
        )

    def to_domain(self) -> ActivityAssetRevision:
        """Restore and revalidate the canonical immutable revision."""
        return ActivityAssetRevision(
            asset_id=self.asset_id,
            revision_number=self.revision_number,
            supersedes_revision_id=self.supersedes_revision_id,
            acquisition=self.acquisition.to_domain(),
            acquisition_shape=self.acquisition_shape,
            asset_kind=self.asset_kind,
            basis=self.basis.to_domain(),
            residual_value=Decimal(self.residual_value.decimal),
            in_service_date=self.in_service_date,
            out_of_service_date=self.out_of_service_date,
            disposal=None if self.disposal is None else self.disposal.to_domain(),
            opening_history=self.opening_history.to_domain(),
            acquired_condition=self.acquired_condition,
            building_construction_date=self.building_construction_date,
            amortization=self.amortization.to_domain(),
            vehicle_affectation=self.vehicle_affectation,
        )

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _canonical(self) -> Self:
        self.to_domain()
        return self


class AmortizationClaimSnapshot(BaseModel):
    """Public recorded claim with every monetary fact represented explicitly."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    asset_id: str = Field(min_length=1, max_length=128)
    asset_revision_id: Hex64Str
    asset_kind: AssetKind
    tax_year: FilingYear
    covered_from: date
    covered_until: date
    amount: PublicDecimal
    schedule_fingerprint: Hex64Str
    authority_generation: str = Field(min_length=1, max_length=256)
    source_reference: str = Field(min_length=1, max_length=2048)
    creating_operation: str = Field(min_length=1, max_length=256)
    supersedes_claim_id: Hex64Str | None = None
    method: AmortizationMethod = AmortizationMethod.LINEAR
    free_depreciation_election_reference: ElectionReference | None = None
    free_depreciation_new_material_evidence_reference: EvidenceReference | None = None
    free_depreciation_unit_acquisition_value: PublicDecimal | None = None
    free_depreciation_annual_cap: PublicDecimal | None = None
    disposal_revision_id: Hex64Str | None = None

    @classmethod
    def from_domain(cls, value: AmortizationClaim) -> Self:
        """Project a canonical history claim to its public wire representation."""
        return cls.model_validate(_public_charge_fields(value))

    def to_domain(self) -> AmortizationClaim:
        """Restore and revalidate the canonical history claim."""
        return AmortizationClaim.model_validate(_domain_charge_fields(self))

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _canonical(self) -> Self:
        self.to_domain()
        return self


class ActivityAssetHistorySnapshot(BaseModel):
    """Closed immutable history with typed revision and claim rows."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    revisions: tuple[ActivityAssetRevisionSnapshot, ...] = ()
    claims: tuple[AmortizationClaimSnapshot, ...] = ()
    descriptors: tuple[ActivityAssetDescriptor, ...] = ()
    events: tuple[ActivityAssetHistoryEvent, ...] = ()

    @classmethod
    def from_domain(cls, value: ActivityAssetHistory) -> Self:
        """Project every canonical revision, claim, descriptor and event in append order."""
        return cls(
            revisions=tuple(ActivityAssetRevisionSnapshot.from_domain(item) for item in value.revisions),
            claims=tuple(AmortizationClaimSnapshot.from_domain(item) for item in value.claims),
            descriptors=value.descriptors,
            events=value.events,
        )

    def to_domain(self) -> ActivityAssetHistory:
        """Restore and validate the complete canonical history graph."""
        return ActivityAssetHistory(
            revisions=tuple(item.to_domain() for item in self.revisions),
            claims=tuple(item.to_domain() for item in self.claims),
            descriptors=self.descriptors,
            events=self.events,
        )

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _canonical(self) -> Self:
        self.to_domain()
        return self


class ScheduledAmortizationChargeSnapshot(BaseModel):
    """Public schedule with typed authority coordinates and decimal outputs."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    asset_id: str = Field(min_length=1, max_length=128)
    asset_revision_id: Hex64Str
    tax_year: FilingYear
    covered_from: date
    covered_until: date
    service_days: int = Field(ge=0)
    calendar_days: int = Field(ge=365, le=366)
    amount: PublicDecimal
    schedule_fingerprint: Hex64Str
    authority_generation: str = Field(min_length=1, max_length=256)
    source_reference: str = Field(min_length=1, max_length=2048)
    method: AmortizationMethod = AmortizationMethod.LINEAR
    annual_rate: PublicDecimal | None = None
    free_depreciation_election_reference: ElectionReference | None = None
    free_depreciation_new_material_evidence_reference: EvidenceReference | None = None
    free_depreciation_unit_acquisition_value: PublicDecimal | None = None
    free_depreciation_annual_cap: PublicDecimal | None = None

    @classmethod
    def from_domain(cls, value: ScheduledAmortizationCharge) -> Self:
        """Project one pinned-authority forecast into the public wire form."""
        return cls.model_validate(_public_charge_fields(value))

    def to_domain(self) -> ScheduledAmortizationCharge:
        """Restore and revalidate the schedule used for claim creation."""
        return ScheduledAmortizationCharge.model_validate(_domain_charge_fields(self))

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _canonical(self) -> Self:
        self.to_domain()
        return self


class ClaimProjectionSnapshot(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    target_casilla_id: str = Field(pattern=r"^0\d{3}$")
    tax_year: FilingYear
    claim_ids: tuple[str, ...]
    amount: PublicDecimal

    @classmethod
    def from_domain(cls, value: ClaimProjection) -> Self:
        return cls(
            target_casilla_id=value.target_casilla_id,
            tax_year=value.tax_year,
            claim_ids=value.claim_ids,
            amount=project_scalar(value.amount),
        )

    def to_domain(self) -> ClaimProjection:
        return ClaimProjection(
            target_casilla_id=self.target_casilla_id,
            tax_year=self.tax_year,
            claim_ids=self.claim_ids,
            amount=Decimal(self.amount.decimal),
        )

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _canonical(self) -> Self:
        self.to_domain()
        return self


def _m130_snapshot(value: M130AccrualProjection) -> ActivityAssetM130ProjectionSnapshot:
    return ActivityAssetM130ProjectionSnapshot(
        tax_year=value.tax_year,
        amount=project_scalar(value.amount),
        contributions=tuple(
            ActivityAssetM130Contribution(
                asset_id=item.asset_id,
                amount=project_scalar(item.amount),
                claim_id=item.claim_id,
                schedule_fingerprint=item.schedule_fingerprint,
            )
            for item in value.contributions
        ),
        unavailable_asset_ids=value.unavailable_asset_ids,
    )


def _m130_domain(value: ActivityAssetM130ProjectionSnapshot) -> M130AccrualProjection:
    return M130AccrualProjection(
        tax_year=value.tax_year,
        amount=Decimal(value.amount.decimal),
        contributions=tuple(
            M130Contribution(
                asset_id=item.asset_id,
                amount=Decimal(item.amount.decimal),
                claim_id=item.claim_id,
                schedule_fingerprint=item.schedule_fingerprint,
            )
            for item in value.contributions
        ),
        unavailable_asset_ids=value.unavailable_asset_ids,
    )


class ActivityAssetFilingHandoffSnapshot(BaseModel):
    """Non-consuming filing projections with explicit decimal amounts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    material_m100: ClaimProjectionSnapshot
    intangible_m100: ClaimProjectionSnapshot
    material_m130: ActivityAssetM130ProjectionSnapshot
    intangible_m130: ActivityAssetM130ProjectionSnapshot

    @classmethod
    def from_domain(cls, value: ActivityAssetFilingHandoff) -> Self:
        """Project the canonical M100 and M130 filing destinations."""
        return cls(
            material_m100=ClaimProjectionSnapshot.from_domain(value.material_m100),
            intangible_m100=ClaimProjectionSnapshot.from_domain(value.intangible_m100),
            material_m130=_m130_snapshot(value.material_m130),
            intangible_m130=_m130_snapshot(value.intangible_m130),
        )

    def to_domain(self) -> ActivityAssetFilingHandoff:
        """Restore all canonical filing projections."""
        return ActivityAssetFilingHandoff(
            material_m100=self.material_m100.to_domain(),
            intangible_m100=self.intangible_m100.to_domain(),
            material_m130=_m130_domain(self.material_m130),
            intangible_m130=_m130_domain(self.intangible_m130),
        )


class ActivityAssetHistoryClaimResultSnapshot(BaseModel):
    """Public claim receipt paired with the complete resulting history."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    history: ActivityAssetHistorySnapshot
    claim: AmortizationClaimSnapshot
    reused_existing_claim: bool

    @classmethod
    def from_domain(cls, value: ActivityAssetHistoryClaimResult) -> Self:
        """Project a canonical claim operation result."""
        return cls(
            history=ActivityAssetHistorySnapshot.from_domain(value.history),
            claim=AmortizationClaimSnapshot.from_domain(value.claim),
            reused_existing_claim=value.reused_existing_claim,
        )

    def to_domain(self) -> ActivityAssetHistoryClaimResult:
        """Restore the typed history and its idempotent-claim disposition."""
        return ActivityAssetHistoryClaimResult(
            history=self.history.to_domain(),
            claim=self.claim.to_domain(),
            reused_existing_claim=self.reused_existing_claim,
        )


__all__ = [
    "ActivityAssetAmortizationElectionSnapshot",
    "ActivityAssetBasisSnapshot",
    "ActivityAssetDisposalSnapshot",
    "ActivityAssetFilingHandoffSnapshot",
    "ActivityAssetHistoryClaimResultSnapshot",
    "ActivityAssetHistorySnapshot",
    "ActivityAssetRevisionSnapshot",
    "AmortizationClaimSnapshot",
    "ScheduledAmortizationChargeSnapshot",
]
