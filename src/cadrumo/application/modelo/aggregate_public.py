"""Strict public operands for the non-invoice modelo aggregation operation.

The operation request schema must not embed domain models with custom scalar
validators.  These DTOs expose ordinary JSON scalars and restore the canonical
domain graph before the aggregation or withholding services run.
"""

from __future__ import annotations

from datetime import date
from typing import Self

from pydantic import BaseModel, Field

from ...core.country_code import COUNTRY_CODE_ALPHA2_PATTERN, CountryCodeAlpha2
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..aggregation.counterpart import CounterpartObservation
from ..aggregation.foreign_assets import ForeignAssetIngestObservation
from ..aggregation.ledger_payment_withholding import LedgerPaymentWithholdingEvidenceRequest
from ..aggregation.service import PerModeloAggregationCommand
from ..aggregation.withholding_observation_service import WithholdingMutationMode
from ..aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from ..operations.public_model_conversion import (
    domain_model_mapping,
    domain_value,
    public_model_mapping,
    public_value,
)
from ..operations.public_period import PublicPeriod
from ..operations.public_scalar import PublicDecimal
from .invoice_withholding_capture_public import (
    PublicAnnualRecipientDetail,
    PublicModelo193PendingPayment,
    PublicWithholdingBaseline,
)


class PublicCounterpartObservation(BaseModel):
    """Counterpart input without custom domain enums or date string hooks."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    source_kind: str = Field(min_length=1, max_length=64)
    source_object_id: str = Field(min_length=1)
    counterparty_nif: str = Field(min_length=1, max_length=20)
    counterparty_name: str = Field(default="", max_length=200)
    counterparty_country: CountryCodeAlpha2 = Field(pattern=COUNTRY_CODE_ALPHA2_PATTERN)
    operation_kind: str = Field(min_length=1)
    operation_period: str = Field(min_length=1, max_length=16)
    taxable_base: PublicDecimal
    invoice_total: PublicDecimal
    accrued_on: date
    groi_verified: bool = False
    nif_iva_verified: bool = False

    @classmethod
    def from_domain(cls, value: CounterpartObservation) -> Self:
        """Copy a canonical counterpart observation into the public DTO."""
        return cls.model_validate(
            {
                **public_model_mapping(value),
                "accrued_on": date.fromisoformat(str(value.accrued_on)),
            },
            strict=True,
        )

    def to_domain(self) -> CounterpartObservation:
        """Restore the canonical country, period and date validations."""
        restored = CounterpartObservation.model_validate(
            {
                **domain_model_mapping(self),
                "accrued_on": self.accrued_on.isoformat(),
            },
            strict=False,
        )
        if type(self).from_domain(restored) != self:
            raise ValueError("counterpart observation must use canonical values")
        return restored


class PublicForeignAssetObservation(BaseModel):
    """Foreign-asset input with public decimal and actual date values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    source_kind: str = Field(min_length=1, max_length=64)
    source_object_id: str = Field(min_length=1, max_length=128)
    asset_class: str = Field(min_length=1, max_length=64)
    asset_external_id: str = Field(min_length=1, max_length=128)
    country: str = Field(pattern=r"^[A-Z]{2}$")
    issuer_or_institution: str = Field(default="", max_length=200)
    valuation_eur: PublicDecimal
    acquisition_date: date
    held_at_year_end: bool = True

    @classmethod
    def from_domain(cls, value: ForeignAssetIngestObservation) -> Self:
        """Copy a canonical foreign-asset observation into the public DTO."""
        return cls.model_validate(
            {
                **public_model_mapping(value),
                "acquisition_date": date.fromisoformat(str(value.acquisition_date)),
            },
            strict=True,
        )

    def to_domain(self) -> ForeignAssetIngestObservation:
        """Restore canonical source, asset-class, country and date validation."""
        restored = ForeignAssetIngestObservation.model_validate(
            {
                **domain_model_mapping(self),
                "acquisition_date": self.acquisition_date.isoformat(),
            },
            strict=False,
        )
        if type(self).from_domain(restored) != self:
            raise ValueError("foreign asset observation must use canonical values")
        return restored


class PublicLedgerPaymentEvidenceRequest(BaseModel):
    """Complete ledger-payment terms as a strict, hidden-input DTO."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: TransactionId
    income_kind: WithholdingIncomeKind
    scheme: str = Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
    recipient_tax_status: WithholdingRecipientTaxStatus
    recipient_tax_regime: WithholdingRecipientTaxRegime
    payment_event_id: str = Field(min_length=1, max_length=128)
    allocation_id: str = Field(min_length=1, max_length=128)
    gross_base: PublicDecimal
    withholding_amount: PublicDecimal
    net_settlement: PublicDecimal
    idempotency_key: str
    mode: WithholdingMutationMode = WithholdingMutationMode.APPEND
    baseline: PublicWithholdingBaseline | None = None
    reason: str | None = None
    supersedes_generation_id: str | None = None
    modelo_190_detail: PublicAnnualRecipientDetail | None = None
    perceptor_nif: str | None = Field(default=None, min_length=1, max_length=16)
    perceptor_name: str | None = Field(default=None, max_length=200)
    exigibility_event_id: str | None = Field(default=None, min_length=1, max_length=128)
    exigibility_occurred_on: date | None = None
    modelo_193_pending_payment: PublicModelo193PendingPayment | None = None

    @classmethod
    def from_domain(cls, value: LedgerPaymentWithholdingEvidenceRequest) -> Self:
        """Copy caller evidence into its closed public scalar graph."""
        result = cls.model_validate(public_value(value), strict=False)
        restored = LedgerPaymentWithholdingEvidenceRequest.model_validate(domain_value(result), strict=False)
        if restored != value:
            raise ValueError("ledger-payment evidence must use canonical values")
        return result

    def to_domain(self) -> LedgerPaymentWithholdingEvidenceRequest:
        """Revalidate the public graph under the shared capture request contract."""
        restored = LedgerPaymentWithholdingEvidenceRequest.model_validate(domain_value(self), strict=False)
        round_trip = type(self).model_validate(public_value(restored), strict=False)
        if round_trip != self:
            raise ValueError("ledger-payment evidence must use canonical values")
        return restored


class PublicModeloAggregateCommand(BaseModel):
    """Caller-authored observation families and one canonical filing period.

    Retención rows are never caller-authored: the operation reads them from the
    stored windows and annual sources the calculation itself reads.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: str = Field(min_length=1, max_length=16)
    period: PublicPeriod
    counterpart_observations: tuple[PublicCounterpartObservation, ...] = Field(default_factory=tuple, repr=False)
    foreign_asset_observations: tuple[PublicForeignAssetObservation, ...] = Field(default_factory=tuple, repr=False)

    @classmethod
    def from_domain(cls, command: PerModeloAggregationCommand) -> Self:
        """Copy the typed aggregation command without custom domain schemas."""
        if command.retencion_observations:
            raise ValueError("retención observations are read from storage, not accepted by modelo aggregate")
        return cls(
            modelo=command.modelo,
            period=PublicPeriod.from_period(command.period),
            counterpart_observations=tuple(
                PublicCounterpartObservation.from_domain(value) for value in command.counterpart_observations
            ),
            foreign_asset_observations=tuple(
                PublicForeignAssetObservation.from_domain(value) for value in command.foreign_asset_observations
            ),
        )

    def to_domain(self) -> PerModeloAggregationCommand:
        """Restore canonical domain rows before any provider is evaluated."""
        return PerModeloAggregationCommand(
            modelo=self.modelo,
            period=self.period.to_period(),
            counterpart_observations=tuple(value.to_domain() for value in self.counterpart_observations),
            foreign_asset_observations=tuple(value.to_domain() for value in self.foreign_asset_observations),
        )


__all__ = [
    "PublicCounterpartObservation",
    "PublicForeignAssetObservation",
    "PublicLedgerPaymentEvidenceRequest",
    "PublicModeloAggregateCommand",
]
