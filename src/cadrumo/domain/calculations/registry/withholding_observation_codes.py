"""Validate withholding observation codes against the governed form catalogue."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from .errors import RegistryValidationError
from .form_codes import FormCodes, resolve_form_codes

_OBSERVATION_COUNT_FIELDS = frozenset(
    {
        "descendants_under_3_total",
        "descendants_under_3_whole",
        "descendants_rest_total",
        "descendants_rest_whole",
        "descendants_disabled_33_65_total",
        "descendants_disabled_33_65_whole",
        "descendants_disabled_mobility_total",
        "descendants_disabled_mobility_whole",
        "descendants_disabled_65_plus_total",
        "descendants_disabled_65_plus_whole",
        "ascendants_under_75_total",
        "ascendants_under_75_whole",
        "ascendants_75_plus_total",
        "ascendants_75_plus_whole",
        "ascendants_disabled_33_65_total",
        "ascendants_disabled_33_65_whole",
        "ascendants_disabled_mobility_total",
        "ascendants_disabled_mobility_whole",
        "ascendants_disabled_65_plus_total",
        "ascendants_disabled_65_plus_whole",
    }
)
OBSERVATION_CODE_FIELDS = (
    "territorial_deduction_clave",
    "perceptor_situacion_familiar",
    "disability_clave",
    "contract_relation_clave",
    "unit_convivencia_titular_clave",
    "geographic_mobility_clave",
    "first_child_compute",
    "second_child_compute",
    "third_child_compute",
    "housing_loan_communication_clave",
    "complemento_infancia_clave",
    "emerging_stock_excess_clave",
    "startup_fund_rendimientos_clave",
    "pension_prestacion_jubilacion",
    "pension_prestacion_viudedad",
    "pension_prestacion_incapacidad",
    "pension_prestacion_no_contributiva",
    "pension_prestacion_resto",
    "clave_codigo",
    "pago",
    "tipo_percepcion",
    "tipo_codigo",
    "clave_mercado",
    "financial_asset_origin",
    "financial_asset_related_entity",
    *_OBSERVATION_COUNT_FIELDS,
)
#: The Modelo 194 related-entity indicator is written blank when the entity is not related.
_OBSERVATION_BLANK_ADMITTING_FIELDS = frozenset({"financial_asset_related_entity"})
WITHHOLDING_CATALOGUE_FACT = "modelo-190-193-withholding-binding-catalogue"


def validate_observation_form_codes(
    populated: Mapping[str, object], financial_asset_origin: str | None, clave_codigo: int | None
) -> None:
    """Refuse codes and counts absent from the published record design."""
    if all(value is None for value in populated.values()):
        return
    declared = resolve_form_codes(WITHHOLDING_CATALOGUE_FACT)
    for name, value in populated.items():
        _validate_observation_code(name, value, declared)
    if (
        financial_asset_origin is not None
        and clave_codigo is not None
        and str(clave_codigo) not in declared.codes("modelo.194.clave_codigo")
    ):
        raise RegistryValidationError("clave_codigo is not a code the Modelo 194 record design declares")


def _validate_observation_code(name: str, value: object, declared: FormCodes) -> None:
    if value is None or (value == "" and name in _OBSERVATION_BLANK_ADMITTING_FIELDS):
        return
    if name in _OBSERVATION_COUNT_FIELDS:
        if not isinstance(value, int) or not 0 <= value <= declared.integer(f"observation_count.{name}.maximum"):
            raise RegistryValidationError(f"{name} exceeds the width the record design declares")
    elif str(value) not in declared.codes(f"observation_code.{name}"):
        raise RegistryValidationError(f"{name} is not a code the record design declares")


def validate_financial_asset_conditions(
    origin: str | None, acquisition: Decimal | None, disposal: Decimal | None, base: Decimal, withholding: Decimal
) -> None:
    """Preserve the source design's absent amounts and negative-base rule."""
    if (
        origin is not None
        and origin == resolve_form_codes(WITHHOLDING_CATALOGUE_FACT).code("modelo.194.origin.without_values")
        and (acquisition is not None or disposal is not None)
    ):
        raise RegistryValidationError("financial-asset origin D requires absent acquisition and disposal values")
    if origin is not None and base < 0 and withholding != 0:
        raise RegistryValidationError("a negative financial-asset withholding base requires zero withholding")
