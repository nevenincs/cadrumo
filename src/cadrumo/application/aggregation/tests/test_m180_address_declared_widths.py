"""The Modelo 180 address refuses what its export design cannot hold."""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.form_codes import resolve_form_codes
from ..retenciones import Modelo180StructuredAddress

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


_MODELO_180 = Path(__file__).resolve().parents[3] / "_data" / "registry" / "aeat" / "modelos" / "180" / "revisions"
_DESIGN_FIELD = {
    "municipality": "municipio",
    "locality": "localidad",
    "street_type": "tipo-via",
    "street_name": "nombre-via",
    "number_type": "tipo-numeracion",
    "house_number": "numero-casa",
    "number_qualifier": "calificador-numero",
    "block": "bloque",
    "portal": "portal",
    "staircase": "escalera",
    "floor": "planta",
    "door": "puerta",
    "complement": "complemento",
}


def _design_fields(node: object) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        if "length" in node:
            yield node
        for value in node.values():
            yield from _design_fields(value)
    elif isinstance(node, list):
        for value in node:
            yield from _design_fields(value)


def _valid_address() -> dict[str, str]:
    return {
        "province_code": "28",
        "municipality_code": "28079",
        "municipality": "M",
        "locality": "M",
        "postal_code": "28001",
        "street_type": "CL",
        "street_name": "S",
        "number_type": "NUM",
        "house_number": "1",
    }


def _declared(field: str) -> int:
    return int(resolve_form_codes("form-row-codes").code(f"m180.address.{field}"))


@pytest.mark.parametrize("code", ["079", "28", "2807", "280790", "99079"])
def test_a_municipality_code_that_is_not_an_ine_code_is_refused(code: str) -> None:
    with pytest.raises(ValidationError):
        Modelo180StructuredAddress(**{**_valid_address(), "municipality_code": code})


def test_a_municipality_outside_the_province_is_refused() -> None:
    with pytest.raises(ValidationError, match="start with the province"):
        Modelo180StructuredAddress(**{**_valid_address(), "municipality_code": "08019"})


def test_the_municipality_code_fills_the_positions_the_design_declares() -> None:
    code = Modelo180StructuredAddress(**_valid_address()).municipality_code
    for design in _MODELO_180.glob("*/export/0002-record-modelo-180-perceptor.toml"):
        fields = _design_fields(tomllib.loads(design.read_text(encoding="utf-8")))
        assert [item["length"] for item in fields if item.get("id") == "modelo-180-perc-inmueble-codigo-municipio"] == [
            len(code)
        ]


@pytest.mark.parametrize("field", sorted(_DESIGN_FIELD))
def test_each_address_field_is_bounded_by_its_declared_width(field: str) -> None:
    limit = _declared(field)
    assert getattr(Modelo180StructuredAddress(**{**_valid_address(), field: "A" * limit}), field) == "A" * limit
    with pytest.raises(ValidationError):
        Modelo180StructuredAddress(**{**_valid_address(), field: "A" * (limit + 1)})


@pytest.mark.parametrize("field", sorted(_DESIGN_FIELD))
def test_each_declared_width_is_the_export_design_width(field: str) -> None:
    designs = tuple(_MODELO_180.glob("*/export/0002-record-modelo-180-perceptor.toml"))
    assert designs
    for design in designs:
        fields = _design_fields(tomllib.loads(design.read_text(encoding="utf-8")))
        name = f"modelo-180-perc-inmueble-{_DESIGN_FIELD[field]}"
        assert [item["length"] for item in fields if item.get("id") == name] == [_declared(field)]
