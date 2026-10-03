"""Closed wire models for canonical spreadsheet observation facts."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from ...core.country_code import CountryCodeAlpha2
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.detail_record_bindings import (
    AtributionMemberObservation,
    Modelo720RowObservation,
)
from ...domain.calculations.registry.gasto193_bindings import Gasto193Observation
from ...domain.calculations.registry.withholding296_bindings import Withholding296Observation
from ...domain.calculations.registry.withholding_bindings import WithholdingObservation

_Text = Annotated[str, Field(max_length=4096)]


class SpreadsheetWithholdingObservation(BaseModel):
    """Closed wire fields of the canonical WithholdingObservation; no copied business policy."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    source_id: _Text
    source_allocation_id: _Text
    perceptor_tax_id: _Text
    perceptor_legal_name: _Text
    country_code: CountryCodeAlpha2 | None
    transaction_date: _Text
    clave: _Text
    subclave: _Text
    percibido_dinerario: _Text
    percibido_especie: _Text
    retencion_practicada: _Text
    ingreso_a_cuenta: _Text
    province_code: _Text | None
    territorial_deduction_clave: int | None
    perceptor_birth_year: int | None
    perceptor_situacion_familiar: int | None
    representative_tax_id: _Text | None
    spouse_or_unit_titular_tax_id: _Text | None
    disability_clave: int | None
    contract_relation_clave: int | None
    unit_convivencia_titular_clave: int | None
    geographic_mobility_clave: int | None
    ingreso_a_cuenta_repercutido: _Text
    accrual_year: int | None
    reducciones_aplicables: _Text
    gastos_deducibles: _Text
    pension_compensatoria: _Text
    anualidades_alimentos: _Text
    descendants_under_3_total: int | None
    descendants_under_3_whole: int | None
    descendants_rest_total: int | None
    descendants_rest_whole: int | None
    descendants_disabled_33_65_total: int | None
    descendants_disabled_33_65_whole: int | None
    descendants_disabled_mobility_total: int | None
    descendants_disabled_mobility_whole: int | None
    descendants_disabled_65_plus_total: int | None
    descendants_disabled_65_plus_whole: int | None
    ascendants_under_75_total: int | None
    ascendants_under_75_whole: int | None
    ascendants_75_plus_total: int | None
    ascendants_75_plus_whole: int | None
    ascendants_disabled_33_65_total: int | None
    ascendants_disabled_33_65_whole: int | None
    ascendants_disabled_mobility_total: int | None
    ascendants_disabled_mobility_whole: int | None
    ascendants_disabled_65_plus_total: int | None
    ascendants_disabled_65_plus_whole: int | None
    first_child_compute: int | None
    second_child_compute: int | None
    third_child_compute: int | None
    housing_loan_communication_clave: int | None
    incapacity_cash_perception: _Text
    incapacity_cash_withholding: _Text
    incapacity_kind_value: _Text
    incapacity_kind_ingreso_a_cuenta: _Text
    incapacity_kind_repercutido: _Text
    complemento_infancia_clave: int | None
    foral_retention_estatal: _Text
    foral_retention_navarra: _Text
    foral_retention_araba: _Text
    foral_retention_gipuzkoa: _Text
    foral_retention_bizkaia: _Text
    emerging_stock_excess_clave: int | None
    startup_fund_rendimientos_clave: int | None
    pension_prestacion_jubilacion: int | None
    pension_prestacion_viudedad: int | None
    pension_prestacion_incapacidad: int | None
    pension_prestacion_no_contributiva: int | None
    pension_prestacion_resto: int | None
    perceptor_mediador_flag: _Text | None
    clave_codigo: int | None
    codigo_emisor: _Text | None
    naturaleza: _Text | None
    pago: int | None
    tipo_codigo: _Text | None
    codigo_cuenta: _Text | None
    pendiente_flag: _Text | None
    tipo_percepcion: int | None
    reducciones: _Text
    base_retenciones: _Text
    porcentaje_retencion: _Text
    penalizaciones: _Text
    isin_code: _Text | None
    naturaleza_declarante: _Text | None
    fecha_inicio_prestamo: _Text | None
    fecha_vencimiento_prestamo: _Text | None
    compensaciones: _Text
    garantias: _Text
    nif_pagador_anterior: _Text | None
    fecha_devengo: _Text | None
    clave_mercado: _Text | None
    numero_orden: int | None


class SpreadsheetModelo720RowObservation(BaseModel):
    """Closed wire fields of the canonical Modelo720RowObservation; no copied business policy."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    source_id: _Text
    asset_class_code: _Text
    country_code: CountryCodeAlpha2
    currency_code: _Text
    asset_identifier: _Text
    acquisition_date: _Text
    valuation_amount: _Text


class SpreadsheetAtributionMemberObservation(BaseModel):
    """Closed wire fields of the canonical AtributionMemberObservation; no copied business policy."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    source_id: _Text
    member_tax_id: _Text
    member_legal_name: _Text
    country_code: CountryCodeAlpha2 | None
    transaction_date: _Text
    share_percentage: _Text
    base_imponible_assigned: _Text
    clave: _Text
    subclave: _Text | None
    codigo_provincia: _Text | None
    miembro_a_31_diciembre: _Text | None
    dias_miembro: int | None
    domicilio_fiscal: _Text | None
    naturaleza_inmueble: _Text | None
    situacion_inmueble: _Text | None
    referencia_catastral: _Text | None
    clave_declarado: _Text | None
    porcentaje_titularidad_inmueble: _Text | None
    dias_arrendamiento: int | None
    reduccion: _Text | None
    rendimiento_neto_previo_eo: _Text | None
    rendimiento_neto_minorado_agricola_eo: _Text | None


class SpreadsheetGasto193Observation(BaseModel):
    """Closed wire fields of the canonical Gasto193Observation; no copied business policy."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    source_id: _Text
    contributor_tax_id: _Text
    contributor_legal_name: _Text
    representative_tax_id: _Text | None
    transaction_date: _Text
    importe_gastos: _Text


class SpreadsheetWithholding296Observation(BaseModel):
    """Closed wire fields of the canonical Withholding296Observation; no copied business policy."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    source_id: _Text
    perceptor_tax_id: _Text
    representative_tax_id: _Text | None
    persona_juridica_flag: _Text | None
    perceptor_legal_name: _Text
    codigo_bic: _Text | None
    fecha_devengo: _Text | None
    naturaleza: _Text
    clave: _Text
    subclave: _Text
    base_retenciones: _Text
    porcentaje_retencion: _Text
    retencion_practicada: _Text
    perceptor_mediador_flag: _Text | None
    codigo: _Text | None
    codigo_emisor: _Text | None
    pago: int | None
    tipo_codigo: _Text | None
    codigo_cuenta: _Text | None
    pendiente_flag: _Text | None
    accrual_year: int | None
    fecha_inicio_prestamo: _Text | None
    fecha_vencimiento_prestamo: _Text | None
    compensaciones: _Text
    garantias: _Text
    otros_importes: _Text
    direccion_perceptor: _Text | None
    ingreso_a_cuenta_repercutido: _Text
    nif_pagador_anterior: _Text | None
    procedimiento_especial_flag: _Text | None
    clave_mercado: _Text | None
    codigo_lei: _Text | None
    nif_pais_residencia: _Text | None
    fecha_nacimiento: _Text | None
    ciudad_nacimiento: _Text | None
    codigo_pais: CountryCodeAlpha2 | None
    pais_residencia_fiscal: CountryCodeAlpha2 | None
    transaction_date: _Text


type SpreadsheetAssembledObservation = (
    SpreadsheetWithholdingObservation
    | SpreadsheetModelo720RowObservation
    | SpreadsheetAtributionMemberObservation
    | SpreadsheetGasto193Observation
    | SpreadsheetWithholding296Observation
)

type CanonicalSpreadsheetAssembledObservation = (
    WithholdingObservation
    | Modelo720RowObservation
    | AtributionMemberObservation
    | Gasto193Observation
    | Withholding296Observation
)


def project_modelo_spreadsheet_observation(
    observation: CanonicalSpreadsheetAssembledObservation,
) -> SpreadsheetAssembledObservation:
    """Losslessly project an already-validated canonical row into its closed wire type."""
    models = (
        (WithholdingObservation, SpreadsheetWithholdingObservation),
        (Modelo720RowObservation, SpreadsheetModelo720RowObservation),
        (AtributionMemberObservation, SpreadsheetAtributionMemberObservation),
        (Gasto193Observation, SpreadsheetGasto193Observation),
        (Withholding296Observation, SpreadsheetWithholding296Observation),
    )
    for canonical_type, wire_type in models:
        if type(observation) is canonical_type:
            return wire_type.model_validate(observation.model_dump(mode="json"), strict=True)
    raise TypeError("unsupported canonical spreadsheet observation")


__all__ = [
    "CanonicalSpreadsheetAssembledObservation",
    "SpreadsheetAssembledObservation",
    "SpreadsheetAtributionMemberObservation",
    "SpreadsheetGasto193Observation",
    "SpreadsheetModelo720RowObservation",
    "SpreadsheetWithholding296Observation",
    "SpreadsheetWithholdingObservation",
    "project_modelo_spreadsheet_observation",
]
