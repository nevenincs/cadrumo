"""Strict Modelo 347 per-counterparty records."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_CENT = Decimal("0.01")


class ClaveOperacion(StrEnum):
    """Closed Modelo 347 operation-key catalogue."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"


class Modelo347RecordLine(BaseModel):
    """One Modelo 347 declared-person detail line."""

    model_config = _STRICT_FROZEN

    record_type: Literal["2"] = "2"
    modelo: Literal["347"] = "347"
    ejercicio: int | None = Field(default=None, ge=2000, le=2099)
    declarant_tax_id: str | None = Field(default=None, min_length=1, max_length=16)
    declared_tax_id: str | None = Field(default=None, min_length=1, max_length=16)
    eu_vat_operator_id: str | None = Field(default=None, min_length=1, max_length=17)
    declared_name: str = Field(min_length=1, max_length=80)
    operation_key: ClaveOperacion
    annual_operation_amount: Decimal
    first_quarter_amount: Decimal | None = None
    second_quarter_amount: Decimal | None = None
    third_quarter_amount: Decimal | None = None
    fourth_quarter_amount: Decimal | None = None
    province_code: str | None = Field(default=None, min_length=2, max_length=2)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    representative_tax_id: str | None = Field(default=None, min_length=1, max_length=16)
    insurance_operation: bool = False
    business_premises_rental: bool = False
    cash_received_amount: Decimal = Decimal("0.00")
    cash_origin_year: int | None = Field(default=None, ge=2000, le=2099)
    real_estate_transmission_amount: Decimal = Decimal("0.00")
    first_quarter_real_estate_transmission_amount: Decimal | None = None
    second_quarter_real_estate_transmission_amount: Decimal | None = None
    third_quarter_real_estate_transmission_amount: Decimal | None = None
    fourth_quarter_real_estate_transmission_amount: Decimal | None = None
    cash_accounting_iva: bool = False
    reverse_charge_operation: bool = False
    non_customs_deposit_operation: bool = False
    cash_accounting_annual_amount: Decimal | None = None
    bdns_call_number: str | None = Field(default=None, min_length=1, max_length=6)
    operation_date: date | None = None
    autonomous_community_code: str | None = Field(default=None, min_length=2, max_length=2)

    @field_validator(
        "annual_operation_amount",
        "first_quarter_amount",
        "second_quarter_amount",
        "third_quarter_amount",
        "fourth_quarter_amount",
        "cash_received_amount",
        "real_estate_transmission_amount",
        "first_quarter_real_estate_transmission_amount",
        "second_quarter_real_estate_transmission_amount",
        "third_quarter_real_estate_transmission_amount",
        "fourth_quarter_real_estate_transmission_amount",
        "cash_accounting_annual_amount",
    )
    @classmethod
    def _require_cent_precision(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if value != value.quantize(_CENT):
            raise ValueError("monetary values must have cent precision")
        return value

    @field_validator("declarant_tax_id", "declared_tax_id", "representative_tax_id", "eu_vat_operator_id", mode="after")
    @classmethod
    def _normalise_tax_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalised = value.strip().upper()
        if not normalised:
            raise ValueError("tax identifiers must not be blank")
        return normalised

    @field_validator("declared_name", mode="after")
    @classmethod
    def _normalise_name(cls, value: str) -> str:
        normalised = " ".join(value.strip().split())
        if not normalised:
            raise ValueError("declared_name must not be blank")
        return normalised

    @model_validator(mode="after")
    def _quarters_match_annual_when_complete(self) -> Modelo347RecordLine:
        quarters = (
            self.first_quarter_amount,
            self.second_quarter_amount,
            self.third_quarter_amount,
            self.fourth_quarter_amount,
        )
        if all(q is not None for q in quarters):
            quarter_sum = sum((q for q in quarters if q is not None), Decimal("0.00"))
            if abs(quarter_sum - self.annual_operation_amount) > _CENT:
                raise ValueError("quarterly amounts must sum to annual_operation_amount within 0.01")
        if self.cash_received_amount > Decimal("0.00") and self.cash_origin_year is None:
            raise ValueError("cash_origin_year is required when cash_received_amount is positive")
        if self.declared_tax_id and self.eu_vat_operator_id:
            raise ValueError("declared_tax_id and eu_vat_operator_id are mutually exclusive")
        if self.declared_tax_id is None and self.eu_vat_operator_id is None:
            raise ValueError("either declared_tax_id or eu_vat_operator_id is required")
        if self.operation_key is ClaveOperacion.E and self.bdns_call_number is None:
            raise ValueError("bdns_call_number is required for operation key E")
        return self


class Modelo347SchemaManifest(BaseModel):
    """Per-year Modelo 347 schema manifest."""

    model_config = _STRICT_FROZEN

    ejercicio: int = Field(ge=2000, le=2099)
    threshold_amount: Decimal
    summary_count_casilla: str = "01"
    summary_total_casilla: str = "02"
    summary_cash_count_casilla: str = "03"
    summary_cash_total_casilla: str = "04"
    operation_keys: tuple[ClaveOperacion, ...]
    record_fields: tuple[str, ...]
    source: str = Field(min_length=1)

    @field_validator("threshold_amount")
    @classmethod
    def _threshold_cent_precision(cls, value: Decimal) -> Decimal:
        if value != value.quantize(_CENT):
            raise ValueError("threshold_amount must have cent precision")
        return value


__all__ = ["ClaveOperacion", "Modelo347RecordLine", "Modelo347SchemaManifest"]
