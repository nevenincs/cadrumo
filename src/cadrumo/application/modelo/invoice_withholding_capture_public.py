"""Explicit public operands for received-invoice withholding capture.

The transport graph uses ordinary scalars and public decimal/period wrappers.
Canonical aggregation and withholding models are restored before service use.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Literal, Self, cast

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from ..aggregation.retenciones import Modelo193NonpaymentCause
from ..aggregation.service import PerModeloAggregationCommand
from ..aggregation.withholding_observation_service import WithholdingMutationMode
from ..aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from ..operations.public_period import PublicPeriod
from ..operations.public_scalar import PublicDecimal


def _public_value(value: object) -> object:
    """Copy one domain value into a public DTO without implicit scalar coercion."""
    if isinstance(value, Decimal):
        return PublicDecimal(decimal=str(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return {name: _public_value(getattr(value, name)) for name in type(value).model_fields}
    if isinstance(value, tuple):
        return tuple(_public_value(item) for item in cast(tuple[object, ...], value))
    return value


def _domain_value(value: object) -> object:
    """Restore public decimal wrappers before canonical domain validation."""
    if isinstance(value, PublicDecimal):
        return Decimal(value.decimal)
    if isinstance(value, BaseModel):
        return {name: _domain_value(getattr(value, name)) for name in type(value).model_fields}
    if isinstance(value, tuple):
        return tuple(_domain_value(item) for item in cast(tuple[object, ...], value))
    return value


class PublicAnnualRecipientDetail(BaseModel):
    """Every annual-recipient fact, with custom domain scalars represented plainly."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    # Explicit fields are kept in the same order as WithholdingObservation.
    source_id: str = Field(min_length=1, max_length=128)
    source_allocation_id: str = Field(default="", max_length=128)
    perceptor_tax_id: str = Field(min_length=1, max_length=64)
    perceptor_legal_name: str = Field(default="", max_length=200)
    country_code: str | None = None
    transaction_date: date
    clave: str
    subclave: str = Field(default="", max_length=4, pattern="^[0-9]*$")
    percibido_dinerario: PublicDecimal = PublicDecimal(decimal="0")
    percibido_especie: PublicDecimal = PublicDecimal(decimal="0")
    retencion_practicada: PublicDecimal = PublicDecimal(decimal="0")
    ingreso_a_cuenta: PublicDecimal = PublicDecimal(decimal="0")
    province_code: str | None = Field(default=None, pattern="^\\d{2}$")
    territorial_deduction_clave: int | None = Field(default=None, ge=0, le=2)
    perceptor_birth_year: int | None = Field(default=None, ge=1900, le=2100)
    perceptor_situacion_familiar: int | None = Field(default=None, ge=1, le=3)
    representative_tax_id: str | None = Field(default=None, min_length=9, max_length=9)
    spouse_or_unit_titular_tax_id: str | None = Field(default=None, min_length=9, max_length=9)
    disability_clave: int | None = Field(default=None, ge=0, le=3)
    contract_relation_clave: int | None = Field(default=None, ge=1, le=4)
    unit_convivencia_titular_clave: int | None = Field(default=None, ge=1, le=2)
    geographic_mobility_clave: int | None = Field(default=None, ge=0, le=1)
    ingreso_a_cuenta_repercutido: PublicDecimal = PublicDecimal(decimal="0")
    accrual_year: int | None = Field(default=None, ge=1900, le=2100)
    reducciones_aplicables: PublicDecimal = PublicDecimal(decimal="0")
    gastos_deducibles: PublicDecimal = PublicDecimal(decimal="0")
    pension_compensatoria: PublicDecimal = PublicDecimal(decimal="0")
    anualidades_alimentos: PublicDecimal = PublicDecimal(decimal="0")
    descendants_under_3_total: int | None = Field(default=None, ge=0, le=9)
    descendants_under_3_whole: int | None = Field(default=None, ge=0, le=9)
    descendants_rest_total: int | None = Field(default=None, ge=0, le=99)
    descendants_rest_whole: int | None = Field(default=None, ge=0, le=99)
    descendants_disabled_33_65_total: int | None = Field(default=None, ge=0, le=99)
    descendants_disabled_33_65_whole: int | None = Field(default=None, ge=0, le=99)
    descendants_disabled_mobility_total: int | None = Field(default=None, ge=0, le=99)
    descendants_disabled_mobility_whole: int | None = Field(default=None, ge=0, le=99)
    descendants_disabled_65_plus_total: int | None = Field(default=None, ge=0, le=99)
    descendants_disabled_65_plus_whole: int | None = Field(default=None, ge=0, le=99)
    ascendants_under_75_total: int | None = Field(default=None, ge=0, le=9)
    ascendants_under_75_whole: int | None = Field(default=None, ge=0, le=9)
    ascendants_75_plus_total: int | None = Field(default=None, ge=0, le=9)
    ascendants_75_plus_whole: int | None = Field(default=None, ge=0, le=9)
    ascendants_disabled_33_65_total: int | None = Field(default=None, ge=0, le=9)
    ascendants_disabled_33_65_whole: int | None = Field(default=None, ge=0, le=9)
    ascendants_disabled_mobility_total: int | None = Field(default=None, ge=0, le=9)
    ascendants_disabled_mobility_whole: int | None = Field(default=None, ge=0, le=9)
    ascendants_disabled_65_plus_total: int | None = Field(default=None, ge=0, le=9)
    ascendants_disabled_65_plus_whole: int | None = Field(default=None, ge=0, le=9)
    first_child_compute: int | None = Field(default=None, ge=1, le=2)
    second_child_compute: int | None = Field(default=None, ge=1, le=2)
    third_child_compute: int | None = Field(default=None, ge=1, le=2)
    housing_loan_communication_clave: int | None = Field(default=None, ge=0, le=1)
    incapacity_cash_perception: PublicDecimal
    incapacity_cash_withholding: PublicDecimal
    incapacity_kind_value: PublicDecimal
    incapacity_kind_ingreso_a_cuenta: PublicDecimal
    incapacity_kind_repercutido: PublicDecimal
    complemento_infancia_clave: int | None = Field(default=None, ge=1, le=2)
    foral_retention_estatal: PublicDecimal
    foral_retention_navarra: PublicDecimal
    foral_retention_araba: PublicDecimal
    foral_retention_gipuzkoa: PublicDecimal
    foral_retention_bizkaia: PublicDecimal
    emerging_stock_excess_clave: int | None = Field(default=None, ge=0, le=1)
    startup_fund_rendimientos_clave: int | None = Field(default=None, ge=0, le=1)
    pension_prestacion_jubilacion: int | None = Field(default=None, ge=0, le=1)
    pension_prestacion_viudedad: int | None = Field(default=None, ge=0, le=1)
    pension_prestacion_incapacidad: int | None = Field(default=None, ge=0, le=1)
    pension_prestacion_no_contributiva: int | None = Field(default=None, ge=0, le=1)
    pension_prestacion_resto: int | None = Field(default=None, ge=0, le=1)
    perceptor_mediador_flag: str | None = Field(default=None, max_length=1)
    clave_codigo: int | None = Field(default=None, ge=1, le=4)
    codigo_emisor: str | None = Field(default=None, max_length=12)
    naturaleza: str | None = Field(default=None, pattern="^\\d{2}$")
    pago: int | None = Field(default=None, ge=1, le=5)
    tipo_codigo: str | None = Field(default=None, pattern="^[COP]$")
    codigo_cuenta: str | None = Field(default=None, max_length=20)
    pendiente_flag: str | None = Field(default=None, max_length=1)
    tipo_percepcion: int | None = Field(default=None, ge=1, le=2)
    reducciones: PublicDecimal = PublicDecimal(decimal="0")
    base_retenciones: PublicDecimal
    porcentaje_retencion: PublicDecimal = PublicDecimal(decimal="0")
    penalizaciones: PublicDecimal = PublicDecimal(decimal="0")
    isin_code: str | None = Field(default=None, max_length=12)
    naturaleza_declarante: str | None = Field(default=None, max_length=1)
    fecha_inicio_prestamo: str | None = Field(default=None, pattern="^\\d{8}$")
    fecha_vencimiento_prestamo: str | None = Field(default=None, pattern="^\\d{8}$")
    compensaciones: PublicDecimal = PublicDecimal(decimal="0")
    garantias: PublicDecimal = PublicDecimal(decimal="0")
    nif_pagador_anterior: str | None = Field(default=None, min_length=9, max_length=9)
    fecha_devengo: str | None = Field(default=None, pattern="^\\d{8}$")
    clave_mercado: str | None = Field(default=None, pattern="^[A-D]$")
    numero_orden: int | None = Field(default=None, ge=1, le=9999999)

    @classmethod
    def from_domain(cls, value: BaseModel) -> Self:
        """Project every canonical annual-recipient field into the public graph."""
        return cls.model_validate(_public_value(value), strict=True)


class PublicModelo180Address(BaseModel):
    """Complete structured property address without domain schema hooks."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    province_code: str = Field(pattern=r"^\d{2}$")
    municipality_code: str = Field(pattern=r"^\d{3}$")
    municipality: str = Field(min_length=1, max_length=30)
    locality: str = Field(min_length=1, max_length=30)
    postal_code: str = Field(pattern=r"^\d{5}$")
    street_type: str = Field(min_length=1, max_length=5)
    street_name: str = Field(min_length=1, max_length=50)
    number_type: str = Field(min_length=1, max_length=3)
    house_number: str = Field(min_length=1, max_length=5)
    number_qualifier: str = Field(default="", max_length=3)
    block: str = Field(default="", max_length=3)
    portal: str = Field(default="", max_length=3)
    staircase: str = Field(default="", max_length=3)
    floor: str = Field(default="", max_length=3)
    door: str = Field(default="", max_length=3)
    complement: str = Field(default="", max_length=40)


class PublicModelo180Property(BaseModel):
    """Complete property evidence in ordinary public scalar types."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    property_key: str = Field(min_length=1, max_length=128)
    situation: Literal["1", "2", "3", "4"]
    cadastral_reference: str | None = Field(default=None, min_length=1, max_length=20)
    address: PublicModelo180Address
    recipient_province_code: str = Field(pattern=r"^\d{2}$")
    modality: Literal["1", "2"]
    accrual_year: int = Field(ge=1900, le=9999)
    withholding_percentage: PublicDecimal
    representative_nif: str | None = Field(default=None, min_length=1, max_length=16)


class PublicModelo193PendingPayment(BaseModel):
    """Complete pending-payment evidence with typed actual-recipient detail."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    perception_key: Literal["A", "B", "D"]
    nonpayment_cause: Modelo193NonpaymentCause
    actual_recipient_detail: PublicAnnualRecipientDetail


class PublicWithholdingBaseline(BaseModel):
    """Portable compare-and-swap coordinates for a withholding window."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    scope_token: str = Field(min_length=1, max_length=256)
    generation_id: str = Field(pattern=r"^[0-9a-f]{64}$")


class PublicInvoiceWithholdingEvidence(BaseModel):
    """Every caller-supplied invoice allocation fact as a typed public operand."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    invoice_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    income_kind: WithholdingIncomeKind
    scheme: str = Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
    recipient_tax_status: WithholdingRecipientTaxStatus
    recipient_tax_regime: WithholdingRecipientTaxRegime
    payment_event_id: str | None = Field(default=None, min_length=1, max_length=128)
    payment_occurred_on: date | None = None
    exigibility_event_id: str | None = Field(default=None, min_length=1, max_length=128)
    exigibility_occurred_on: date | None = None
    allocation_id: str
    allocated_base: PublicDecimal
    allocated_withholding: PublicDecimal
    allocated_settlement: PublicDecimal
    idempotency_key: str
    mode: WithholdingMutationMode = WithholdingMutationMode.APPEND
    baseline: PublicWithholdingBaseline | None = None
    reason: str | None = None
    supersedes_generation_id: str | None = None
    modelo_180_property: PublicModelo180Property | None = None
    modelo_190_detail: PublicAnnualRecipientDetail | None = None
    modelo_193_pending_payment: PublicModelo193PendingPayment | None = None

    @classmethod
    def from_domain(cls, value: InvoiceWithholdingEvidenceRequest) -> Self:
        """Copy every canonical evidence field into the public request graph."""
        # Canonical domain enums are serialized to their public wire values by
        # _public_value. Pydantic restores only the declared closed enum values.
        return cls.model_validate(_public_value(value), strict=False)

    def to_domain(self) -> InvoiceWithholdingEvidenceRequest:
        """Revalidate the complete evidence under the canonical service contract."""
        restored = InvoiceWithholdingEvidenceRequest.model_validate(_domain_value(self), strict=False)
        if type(self).from_domain(restored) != self:
            raise ValueError("invoice withholding evidence must use canonical values")
        return restored


class PublicInvoiceWithholdingCommand(BaseModel):
    """Closed received-invoice command: caller-authored source rows are forbidden."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: Literal["111", "115"]
    period: PublicPeriod

    @classmethod
    def from_domain(cls, value: PerModeloAggregationCommand) -> Self:
        """Reject every caller-authored observation before projecting coordinates."""
        if any(
            (
                value.retencion_observations,
                value.counterpart_observations,
                value.foreign_asset_observations,
            )
        ):
            raise ValueError("received-invoice capture forbids caller-authored observations")
        return cls.model_validate({"modelo": value.modelo, "period": PublicPeriod.from_period(value.period)})

    def to_domain(self) -> PerModeloAggregationCommand:
        """Restore the canonical aggregation command from the closed public shape."""
        return PerModeloAggregationCommand(modelo=self.modelo, period=self.period.to_period())
