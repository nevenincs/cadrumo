"""The identifier widths these models enforce come from the registry, at the real width and past it."""

from __future__ import annotations

import contextvars
import json
from collections.abc import Iterator
from datetime import date
from importlib import import_module

import pytest
from pydantic import BaseModel, ValidationError

from ....contribuyente.descendant import DescendantInfo
from ..authority import bundled_indexed_authority
from ..errors import RegistryValidationError
from ..export_value_policy import ExportValuePolicy
from ..form_codes import resolve_form_codes
from ..nif_iva_catalogue import resolve_nif_iva_catalogue
from ..schema_exports import ExportRecordDefinition
from ..schema_scalars import validate_registry_text_scalar
from ..withholding_bindings import WithholdingObservation
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _NifIva:
    def validate_python(self, raw: object) -> str:
        return validate_registry_text_scalar("nif_iva", raw)


_NIF_IVA = _NifIva()


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
        for definition in resolve_nif_iva_catalogue(
            effective_date=date(filing_year_envelope().horizon, 1, 1)
        ).definitions
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
        with pytest.raises(RegistryValidationError):
            _NIF_IVA.validate_python("BE" + body)


def test_a_signed_component_layout_of_an_undeclared_geometry_is_refused() -> None:
    declared = resolve_form_codes("form-row-codes").codes("export.signed_amount.component_lengths")
    assert declared
    for group in declared:
        widths = tuple(int(width) for width in group.split("."))
        _component_record(widths)
    with pytest.raises(ValidationError, match="adjacent components"):
        _component_record((1, 9, 2))


def _component_record(widths: tuple[int, ...]) -> ExportRecordDefinition:
    policies = (
        ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN,
        ExportValuePolicy.SIGNED_COMPONENT_INTEGER_PART,
        ExportValuePolicy.SIGNED_COMPONENT_FRACTIONAL_DIGITS,
    )
    offset = 1
    fields = []
    for order, (policy, width) in enumerate(zip(policies, widths, strict=True)):
        fields.append(
            {
                "id": f"test.f{order}",
                "offset": offset,
                "length": width,
                "kind": "binding",
                "binding": "test-binding",
                "data_type": "text" if order == 0 else "integer",
                "required": False,
                "padding": "none" if order == 0 else "left_zero",
                "justification": "none" if order == 0 else "right",
                "signed": False,
                "value_policy": policy.value,
                "legal_refs": ["ley-37-1992:art-164"],
                "source_refs": ["aeat-dr-280-2022"],
            }
        )
        offset += width
    return ExportRecordDefinition.model_validate_json(
        json.dumps(
            {
                "id": "test-record",
                "record_type": "declarado",
                "order": 1,
                "encoding": "iso-8859-1",
                "line_ending": "crlf",
                "fields": fields,
            }
        )
    )
