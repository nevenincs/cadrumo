"""The computed IVA kinds hold their bindings to a plain, unaggregated money output."""

from __future__ import annotations

import pytest

from ..bindings import validate_binding_selector_shape
from ..iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_APLICADA_CASILLA,
    M303_COMPENSATION_AVAILABLE_CASILLA,
    M303_COMPENSATION_GENERADA_CASILLA,
    M303_COMPENSATION_POSTERIOR_CASILLA,
)
from .binding_family_support import family_binding

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("registry_authority")]

_QUARTERS = ("1T", "2T", "3T", "4T")

_PARTITION = {
    "kind": "iva_compensation_annual_partition",
    "source_modelo": "303",
    "source_casilla_ids": (
        M303_COMPENSATION_GENERADA_CASILLA,
        M303_COMPENSATION_APLICADA_CASILLA,
        M303_COMPENSATION_AVAILABLE_CASILLA,
        M303_COMPENSATION_POSTERIOR_CASILLA,
    ),
    "source_periods": _QUARTERS,
    "partition_output": "last_period_amount",
}
_PRORRATA = {
    "kind": "prorrata_regularizacion",
    "source_modelo": "303",
    "source_casilla_ids": (
        "iva.cuota-deducible-total",
        "iva.prorrata-volumen-con-derecho",
        "iva.prorrata-volumen-total",
        "iva.prorrata-porcentaje",
    ),
    "source_periods": _QUARTERS,
    "regularizacion_output": "modelo_303_casilla_44",
}
_BIENES = {
    "kind": "bienes_inversion_regularizacion",
    "source_modelo": "303",
    "regularizacion_output": "modelo_303_casilla_43",
}

_PROVIDERS = {
    "iva_compensation_annual_partition": _PARTITION,
    "prorrata_regularizacion": _PRORRATA,
    "bienes_inversion_regularizacion": _BIENES,
}


@pytest.mark.parametrize("kind", sorted(_PROVIDERS))
def test_a_plain_money_output_passes(kind: str) -> None:
    assert validate_binding_selector_shape(family_binding(_PROVIDERS[kind])) == []


@pytest.mark.parametrize("kind", sorted(_PROVIDERS))
def test_a_decimal_value_is_refused(kind: str) -> None:
    binding = family_binding(_PROVIDERS[kind], data_type="decimal", binding_id=f"test.{kind}.decimal")

    failures = validate_binding_selector_shape(binding)

    assert len(failures) == 1
    assert f"test.{kind}.decimal" in failures[0]
    assert "value data_type must be money, not 'decimal'" in failures[0]


@pytest.mark.parametrize("kind", sorted(_PROVIDERS))
def test_an_authored_aggregation_is_refused(kind: str) -> None:
    binding = family_binding(_PROVIDERS[kind], aggregation={"op": "sum"}, binding_id=f"test.{kind}.aggregation")

    failures = validate_binding_selector_shape(binding)

    assert len(failures) == 1
    assert f"test.{kind}.aggregation" in failures[0]
    assert "never reads an aggregation" in failures[0]


@pytest.mark.parametrize("kind", sorted(_PROVIDERS))
def test_both_defects_are_reported_together(kind: str) -> None:
    binding = family_binding(_PROVIDERS[kind], data_type="decimal", aggregation={"op": "sum"})

    assert len(validate_binding_selector_shape(binding)) == 2
