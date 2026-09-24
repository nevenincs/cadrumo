"""The amortization election an immutable activity-asset revision carries.

An election names the direct-estimation modality, the statutory table class
and the depreciation method together with the facts that method needs.  It is
an asset fact: changing it appends a superseding revision whose admissibility
the schedule judges against the claims recorded under earlier elections.
Legal bounds (admission, coefficient ranges, windows, thresholds) are not
decided here; the registry resolver validates the election against published
authority.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.filing_year import FilingYear
from ....core.hashing import content_hash_hex
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.money.rounding import round_to_cents


class DirectEstimationRegime(StrEnum):
    """The two common-regime direct-estimation modalities."""

    NORMAL = "normal"
    SIMPLIFIED = "simplified"


class AmortizationMethod(StrEnum):
    """Every depreciation method or incentive an asset can elect.

    Justified amount, small-enterprise employment, renewable self-consumption
    and entity-regime free depreciation are statutory methods the product
    refuses with a cited reason; they are typed so the refusal is explicit
    rather than an unknown token.
    """

    LINEAR = "linear"
    CONSTANT_PERCENTAGE = "constant_percentage"
    SUM_OF_DIGITS = "sum_of_digits"
    APPROVED_PLAN = "approved_plan"
    INTANGIBLE_USEFUL_LIFE = "intangible_useful_life"
    INTANGIBLE_INDEFINITE_LIFE = "intangible_indefinite_life"
    GOODWILL = "goodwill"
    LOW_VALUE_FREE = "low_value_free"
    RESEARCH_DEVELOPMENT_FREE = "research_development_free"
    RESEARCH_DEVELOPMENT_BUILDING = "research_development_building"
    CHARGING_INFRASTRUCTURE_FREE = "charging_infrastructure_free"
    ELECTRIC_VEHICLE_FREE = "electric_vehicle_free"
    JUSTIFIED_AMOUNT = "justified_amount"
    SMALL_ENTERPRISE_EMPLOYMENT_FREE = "small_enterprise_employment_free"
    RENEWABLE_SELF_CONSUMPTION_FREE = "renewable_self_consumption_free"
    ENTITY_REGIME_FREE = "entity_regime_free"


FREE_AMOUNT_METHODS: frozenset[AmortizationMethod] = frozenset(
    {
        AmortizationMethod.LOW_VALUE_FREE,
        AmortizationMethod.RESEARCH_DEVELOPMENT_FREE,
        AmortizationMethod.CHARGING_INFRASTRUCTURE_FREE,
        AmortizationMethod.ELECTRIC_VEHICLE_FREE,
    },
)
"""Methods whose per-period amount is the taxpayer's bounded choice."""


class AcquiredCondition(StrEnum):
    """Whether the asset was first put into operation by this taxpayer."""

    NEW = "new"
    USED = "used"


class DigitOrder(StrEnum):
    """Sum-of-digits numbering order admitted by RIS art. 6.1.a."""

    DESCENDING = "descending"
    ASCENDING = "ascending"


class PlanApprovalKind(StrEnum):
    """How the administration accepted an amortization plan (RIS art. 7.6-7.7)."""

    EXPRESS = "express"
    AMENDED_WITH_CONSENT = "amended_with_consent"
    SILENCE = "silence"


def _require_cents(value: Decimal, *, allow_zero: bool) -> Decimal:
    if not value.is_finite() or value < Decimal("0") or (not allow_zero and value == Decimal("0")):
        raise ValueError("amount must be a finite non-negative Decimal")
    if value != round_to_cents(value):
        raise ValueError("amount must be rounded to euro cents")
    return value


class PlanAnnualAmount(BaseModel):
    """The amortization an approved plan distributes to one tax year."""

    model_config = STRICT_FROZEN_CONFIG

    tax_year: FilingYear
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def _require_positive_cents(cls, value: Decimal) -> Decimal:
        return _require_cents(value, allow_zero=False)


class ApprovedAmortizationPlan(BaseModel):
    """An administratively approved temporal distribution of amortization."""

    model_config = STRICT_FROZEN_CONFIG

    approval_reference: str = Field(min_length=1, max_length=256)
    approval_kind: PlanApprovalKind
    submitted_on: date
    resolved_on: date
    annual_amounts: tuple[PlanAnnualAmount, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_distribution(self) -> Self:
        if self.resolved_on < self.submitted_on:
            raise ValueError("plan resolution cannot precede its submission")
        years = [item.tax_year for item in self.annual_amounts]
        if len(set(years)) != len(years):
            raise ValueError("plan distribution declares a tax year more than once")
        if years != sorted(years):
            raise ValueError("plan distribution must list tax years in ascending order")
        return self

    def amount_for(self, tax_year: int) -> Decimal | None:
        """Return the approved amount for a tax year, or None when undistributed."""
        return next((item.amount for item in self.annual_amounts if item.tax_year == tax_year), None)

    @property
    def total(self) -> Decimal:
        """Return the sum of every distributed amount."""
        return sum((item.amount for item in self.annual_amounts), Decimal("0"))


class DefiniteUsefulLife(BaseModel):
    """Evidence of the end of an intangible asset's definite useful life."""

    model_config = STRICT_FROZEN_CONFIG

    ends_on: date
    evidence_reference: str = Field(min_length=1, max_length=512)


class SmallEnterpriseEvidence(BaseModel):
    """Evidence that the asset was made available in a reduced-size period."""

    model_config = STRICT_FROZEN_CONFIG

    evidence_reference: str = Field(min_length=1, max_length=512)
    made_available_on: date
    prior_period_net_turnover: Decimal

    @field_validator("prior_period_net_turnover")
    @classmethod
    def _require_cents_turnover(cls, value: Decimal) -> Decimal:
        return _require_cents(value, allow_zero=True)


class LowValueElection(BaseModel):
    """Evidence for the EUR 300 new-material free-depreciation election."""

    model_config = STRICT_FROZEN_CONFIG

    election_reference: str = Field(min_length=1, max_length=256)
    new_material_evidence_reference: str = Field(min_length=1, max_length=512)
    unit_acquisition_value: Decimal

    @field_validator("unit_acquisition_value")
    @classmethod
    def _require_positive_cents(cls, value: Decimal) -> Decimal:
        return _require_cents(value, allow_zero=False)


class ChargingInfrastructureEvidence(BaseModel):
    """The two documents LIS DA 18a.3 requires for charging infrastructure."""

    model_config = STRICT_FROZEN_CONFIG

    technical_documentation_reference: str = Field(min_length=1, max_length=512)
    installation_certificate_reference: str = Field(min_length=1, max_length=512)


class ActivityAssetAmortizationElection(BaseModel):
    """Regime, table class, method and the facts the chosen method requires.

    The structural validator admits each optional fact only for the methods
    that consume it, so an election cannot carry an unused rate lever.
    """

    model_config = STRICT_FROZEN_CONFIG

    regime: DirectEstimationRegime
    method: AmortizationMethod
    authority_class_key: str | None = Field(default=None, min_length=1, max_length=64)
    linear_coefficient: Decimal | None = None
    shift_hours_per_day: Decimal | None = None
    sum_of_digits_period_years: int | None = Field(default=None, ge=1, le=100)
    digit_order: DigitOrder | None = None
    approved_plan: ApprovedAmortizationPlan | None = None
    useful_life: DefiniteUsefulLife | None = None
    small_enterprise: SmallEnterpriseEvidence | None = None
    low_value: LowValueElection | None = None
    research_development_evidence_reference: str | None = Field(default=None, min_length=1, max_length=512)
    charging_infrastructure: ChargingInfrastructureEvidence | None = None

    @field_validator("linear_coefficient")
    @classmethod
    def _require_fraction(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or not Decimal("0") < value <= Decimal("1")):
            raise ValueError("linear_coefficient must be a finite Decimal fraction in (0, 1]")
        return value

    @field_validator("shift_hours_per_day")
    @classmethod
    def _require_multi_shift_hours(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or not Decimal("0") < value <= Decimal("24")):
            raise ValueError("shift_hours_per_day must be a finite Decimal in (0, 24]")
        return value

    @model_validator(mode="after")
    def _validate_method_shape(self) -> Self:
        method = self.method
        self._admit(
            "linear_coefficient",
            self.linear_coefficient,
            {AmortizationMethod.LINEAR, AmortizationMethod.CONSTANT_PERCENTAGE},
        )
        self._admit("shift_hours_per_day", self.shift_hours_per_day, {AmortizationMethod.LINEAR})
        self._admit(
            "small_enterprise",
            self.small_enterprise,
            {
                AmortizationMethod.LINEAR,
                AmortizationMethod.INTANGIBLE_INDEFINITE_LIFE,
                AmortizationMethod.GOODWILL,
            },
        )
        self._admit(
            "sum_of_digits_period_years",
            self.sum_of_digits_period_years,
            {AmortizationMethod.SUM_OF_DIGITS},
        )
        self._admit("digit_order", self.digit_order, {AmortizationMethod.SUM_OF_DIGITS})
        self._admit("approved_plan", self.approved_plan, {AmortizationMethod.APPROVED_PLAN})
        self._admit("useful_life", self.useful_life, {AmortizationMethod.INTANGIBLE_USEFUL_LIFE})
        self._admit("low_value", self.low_value, {AmortizationMethod.LOW_VALUE_FREE})
        self._admit(
            "research_development_evidence_reference",
            self.research_development_evidence_reference,
            {AmortizationMethod.RESEARCH_DEVELOPMENT_FREE, AmortizationMethod.RESEARCH_DEVELOPMENT_BUILDING},
        )
        self._admit(
            "charging_infrastructure",
            self.charging_infrastructure,
            {AmortizationMethod.CHARGING_INFRASTRUCTURE_FREE},
        )
        required: dict[AmortizationMethod, tuple[tuple[str, object], ...]] = {
            AmortizationMethod.LINEAR: (("authority_class_key", self.authority_class_key),),
            AmortizationMethod.CONSTANT_PERCENTAGE: (("authority_class_key", self.authority_class_key),),
            AmortizationMethod.SUM_OF_DIGITS: (
                ("authority_class_key", self.authority_class_key),
                ("sum_of_digits_period_years", self.sum_of_digits_period_years),
                ("digit_order", self.digit_order),
            ),
            AmortizationMethod.APPROVED_PLAN: (("approved_plan", self.approved_plan),),
            AmortizationMethod.INTANGIBLE_USEFUL_LIFE: (("useful_life", self.useful_life),),
            AmortizationMethod.LOW_VALUE_FREE: (("low_value", self.low_value),),
            AmortizationMethod.RESEARCH_DEVELOPMENT_FREE: (
                ("research_development_evidence_reference", self.research_development_evidence_reference),
            ),
            AmortizationMethod.RESEARCH_DEVELOPMENT_BUILDING: (
                ("authority_class_key", self.authority_class_key),
                ("research_development_evidence_reference", self.research_development_evidence_reference),
            ),
            AmortizationMethod.CHARGING_INFRASTRUCTURE_FREE: (
                ("charging_infrastructure", self.charging_infrastructure),
            ),
            AmortizationMethod.ELECTRIC_VEHICLE_FREE: (("authority_class_key", self.authority_class_key),),
        }
        for field_name, value in required.get(method, ()):
            if value is None:
                raise ValueError(f"{method.value} election requires {field_name}")
        if self.shift_hours_per_day is not None and self.small_enterprise is not None:
            raise ValueError("multi-shift and reduced-size acceleration cannot be combined in one election")
        return self

    def _admit(self, field_name: str, value: object, methods: set[AmortizationMethod]) -> None:
        if value is not None and self.method not in methods:
            raise ValueError(f"{field_name} is not a fact of the {self.method.value} method")

    @property
    def fingerprint(self) -> str:
        """Return the stable identity used to judge a change of method."""
        return content_hash_hex(self.model_dump(mode="json"))


__all__ = [
    "FREE_AMOUNT_METHODS",
    "AcquiredCondition",
    "ActivityAssetAmortizationElection",
    "AmortizationMethod",
    "ApprovedAmortizationPlan",
    "ChargingInfrastructureEvidence",
    "DefiniteUsefulLife",
    "DigitOrder",
    "DirectEstimationRegime",
    "LowValueElection",
    "PlanAnnualAmount",
    "PlanApprovalKind",
    "SmallEnterpriseEvidence",
]
