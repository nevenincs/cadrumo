"""The identifier widths these models enforce come from the registry, at the real width and past it."""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from datetime import date
from importlib import import_module

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from ....contribuyente.descendant import DescendantInfo
from ..authority import bundled_indexed_authority
from ..form_codes import resolve_form_codes
from ..nif_iva_catalogue import resolve_nif_iva_catalogue
from ..schema_scalars import NifIvaString
from ..withholding_bindings import WithholdingObservation

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NIF_IVA = TypeAdapter(NifIvaString)


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _tax_id_width() -> int:
    return resolve_form_codes("spanish-tax-identifier-format").integer("tax_id.width")


def _field_refused(model: type[BaseModel], field: str, value: object) -> bool:
    try:
        model.model_validate({field: value})
    except ValidationError as exc:
        return any(error["loc"][0] == field for error in exc.errors())
    return False


@pytest.mark.parametrize("field", ["representative_tax_id", "spouse_or_unit_titular_tax_id", "nif_pagador_anterior"])
def test_a_withholding_party_identifier_has_the_declared_width(field: str) -> None:
    width = _tax_id_width()
    assert not _field_refused(WithholdingObservation, field, "1" * width)
    assert _field_refused(WithholdingObservation, field, "1" * (width + 1))
    assert _field_refused(WithholdingObservation, field, "1" * (width - 1))


def test_a_descendant_identifier_has_the_declared_width() -> None:
    width = _tax_id_width()
    assert not _field_refused(DescendantInfo, "nif", "1" * width)
    assert _field_refused(DescendantInfo, "nif", "1" * (width + 1))
    assert _field_refused(DescendantInfo, "nif", "1" * (width - 1))


def test_a_client_outside_every_scope_keeps_the_technical_bound_only() -> None:
    field = "representative_tax_id"
    bound = WithholdingObservation.model_fields[field].metadata
    capacity = next(item.max_length for item in bound if hasattr(item, "max_length"))
    outside = contextvars.Context()
    assert not outside.run(_field_refused, WithholdingObservation, field, "1" * capacity)
    assert outside.run(_field_refused, WithholdingObservation, field, "1" * (capacity + 1))


def test_the_nif_iva_body_envelope_is_the_catalogue_s_own() -> None:
    """The two bounds are exactly what the country patterns of the fact produce, so neither restates a guess."""
    codes = resolve_form_codes("nif-iva-country-format-catalogue")
    bodies = [
        width
        for definition in resolve_nif_iva_catalogue(effective_date=date(2025, 1, 1)).definitions
        for width in import_module("re._parser").parse(definition.spec.pattern.pattern).getwidth()
    ]
    assert codes.integer("nif_iva.body_min_length") == min(bodies) - 2
    assert codes.integer("nif_iva.body_max_length") == max(bodies) - 2


def test_a_nif_iva_of_a_body_outside_the_envelope_is_refused() -> None:
    codes = resolve_form_codes("nif-iva-country-format-catalogue")
    shortest, longest = codes.integer("nif_iva.body_min_length"), codes.integer("nif_iva.body_max_length")
    assert _NIF_IVA.validate_python("BE" + "1" * shortest) == "BE" + "1" * shortest
    assert _NIF_IVA.validate_python("BE" + "1" * longest) == "BE" + "1" * longest
    for body in ("1" * (shortest - 1), "1" * (longest + 1)):
        with pytest.raises(ValidationError):
            _NIF_IVA.validate_python("BE" + body)
