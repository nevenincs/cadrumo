"""Explicit public operands for received-invoice withholding capture.

The transport graph uses ordinary scalars and public decimal/period wrappers.
Canonical aggregation and withholding models are restored before service use.
"""

from __future__ import annotations

from datetime import date
from typing import Self

from pydantic import BaseModel, Field, field_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.spanish_postcode import SpanishProvinceCode
from ..aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from ..aggregation.retenciones import Modelo180StructuredAddress, Modelo193NonpaymentCause
from ..aggregation.service import PerModeloAggregationCommand
from ..aggregation.withholding_modelo_routing import require_invoice_evidence_modelo
from ..aggregation.withholding_observation_service import WithholdingMutationMode
from ..aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from ..operations.public_model_conversion import domain_value, public_value
from ..operations.public_period import PublicPeriod
from ..operations.public_scalar import PublicDecimal


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
    territorial_deduction_clave: int | None = None
    perceptor_birth_year: int | None = Field(default=None, ge=1900, le=2100)
    perceptor_situacion_familiar: int | None = None
    representative_tax_id: str | None = Field(default=None, min_length=9, max_length=9)
    spouse_or_unit_titular_tax_id: str | None = Field(default=None, min_length=9, max_length=9)
    disability_clave: int | None = None
    contract_relation_clave: int | None = None
    unit_convivencia_titular_clave: int | None = None
    geographic_mobility_clave: int | None = None
    ingreso_a_cuenta_repercutido: PublicDecimal = PublicDecimal(decimal="0")
    accrual_year: int | None = Field(default=None, ge=1900, le=2100)
    reducciones_aplicables: PublicDecimal = PublicDecimal(decimal="0")
    gastos_deducibles: PublicDecimal = PublicDecimal(decimal="0")
    pension_compensatoria: PublicDecimal = PublicDecimal(decimal="0")
    anualidades_alimentos: PublicDecimal = PublicDecimal(decimal="0")
    descendants_under_3_total: int | None = None
    descendants_under_3_whole: int | None = None
    descendants_rest_total: int | None = None
    descendants_rest_whole: int | None = None
    descendants_disabled_33_65_total: int | None = None
    descendants_disabled_33_65_whole: int | None = None
    descendants_disabled_mobility_total: int | None = None
    descendants_disabled_mobility_whole: int | None = None
    descendants_disabled_65_plus_total: int | None = None
    descendants_disabled_65_plus_whole: int | None = None
    ascendants_under_75_total: int | None = None
    ascendants_under_75_whole: int | None = None
    ascendants_75_plus_total: int | None = None
    ascendants_75_plus_whole: int | None = None
    ascendants_disabled_33_65_total: int | None = None
    ascendants_disabled_33_65_whole: int | None = None
    ascendants_disabled_mobility_total: int | None = None
    ascendants_disabled_mobility_whole: int | None = None
    ascendants_disabled_65_plus_total: int | None = None
    ascendants_disabled_65_plus_whole: int | None = None
    first_child_compute: int | None = None
    second_child_compute: int | None = None
    third_child_compute: int | None = None
    housing_loan_communication_clave: int | None = None
    incapacity_cash_perception: PublicDecimal
    incapacity_cash_withholding: PublicDecimal
    incapacity_kind_value: PublicDecimal
    incapacity_kind_ingreso_a_cuenta: PublicDecimal
    incapacity_kind_repercutido: PublicDecimal
    complemento_infancia_clave: int | None = None
    foral_retention_estatal: PublicDecimal
    foral_retention_navarra: PublicDecimal
    foral_retention_araba: PublicDecimal
    foral_retention_gipuzkoa: PublicDecimal
    foral_retention_bizkaia: PublicDecimal
    emerging_stock_excess_clave: int | None = None
    startup_fund_rendimientos_clave: int | None = None
    pension_prestacion_jubilacion: int | None = None
    pension_prestacion_viudedad: int | None = None
    pension_prestacion_incapacidad: int | None = None
    pension_prestacion_no_contributiva: int | None = None
    pension_prestacion_resto: int | None = None
    perceptor_mediador_flag: str | None = Field(default=None, max_length=1)
    clave_codigo: int | None = None
    codigo_emisor: str | None = Field(default=None, max_length=12)
    naturaleza: str | None = Field(default=None, pattern="^\\d{2}$")
    pago: int | None = None
    tipo_codigo: str | None = None
    codigo_cuenta: str | None = Field(default=None, max_length=20)
    financial_asset_origin: str | None = None
    financial_asset_acquisition_value: PublicDecimal | None = None
    financial_asset_disposal_value: PublicDecimal | None = None
    financial_asset_related_entity: str | None = None
    pendiente_flag: str | None = Field(default=None, max_length=1)
    tipo_percepcion: int | None = None
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
    clave_mercado: str | None = None
    numero_orden: int | None = Field(default=None, ge=1, le=9999999)

    @classmethod
    def from_domain(cls, value: BaseModel) -> Self:
        """Project every canonical annual-recipient field into the public graph."""
        return cls.model_validate(public_value(value), strict=True)


class PublicModelo180Address(Modelo180StructuredAddress):
    """Complete structured property address without domain schema hooks."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class PublicModelo180Property(BaseModel):
    """Complete property evidence in ordinary public scalar types."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    property_key: str = Field(min_length=1, max_length=128)
    situation: str = Field(min_length=1)
    cadastral_reference: str | None = Field(default=None, min_length=1, max_length=20)
    address: PublicModelo180Address
    recipient_province_code: SpanishProvinceCode
    modality: str = Field(min_length=1)
    accrual_year: int = Field(ge=1900, le=9999)
    withholding_percentage: PublicDecimal
    representative_nif: str | None = Field(default=None, min_length=1, max_length=16)


class PublicModelo193PendingPayment(BaseModel):
    """Complete pending-payment evidence with typed actual-recipient detail."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    perception_key: str = Field(min_length=1)
    nonpayment_cause: Modelo193NonpaymentCause
    actual_recipient_detail: PublicAnnualRecipientDetail


class PublicWithholdingBaseline(BaseModel):
    """Portable compare-and-swap coordinates for a withholding window."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    scope_token: str = Field(min_length=1, max_length=256)
    generation_id: Hex64Str


class PublicInvoiceWithholdingEvidence(BaseModel):
    """Every caller-supplied invoice allocation fact as a typed public operand."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    invoice_id: Hex64Str
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
        return cls.model_validate(public_value(value), strict=False)

    def to_domain(self) -> InvoiceWithholdingEvidenceRequest:
        """Revalidate the complete evidence under the canonical service contract."""
        restored = InvoiceWithholdingEvidenceRequest.model_validate(domain_value(self), strict=False)
        if type(self).from_domain(restored) != self:
            raise ValueError("invoice withholding evidence must use canonical values")
        return restored


class PublicInvoiceWithholdingCommand(BaseModel):
    """Closed received-invoice command: caller-authored source rows are forbidden."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: str
    period: PublicPeriod

    @field_validator("modelo")
    @classmethod
    @pydantic_validation_boundary
    def _require_invoice_evidence_modelo(cls, value: str) -> str:
        return require_invoice_evidence_modelo(value)

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
