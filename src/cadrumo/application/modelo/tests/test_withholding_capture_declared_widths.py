"""The annual-recipient wire model keeps the widths and ceiling the registry declares for the form."""

from __future__ import annotations

import contextvars
from collections.abc import Iterator

import pytest
from pydantic import BaseModel, ValidationError

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.form_codes import resolve_form_codes
from ....domain.calculations.registry.withholding_bindings import WithholdingObservation
from ..invoice_withholding_capture_public import PublicAnnualRecipientDetail

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _refused(model: type[BaseModel], field: str, value: object) -> bool:
    try:
        model.model_validate({field: value})
    except ValidationError as exc:
        return any(error["loc"][0] == field for error in exc.errors())
    return False


def _declared(key: str) -> int:
    return int(resolve_form_codes("form-row-codes").code(key))


@pytest.mark.parametrize(
    ("field", "key"),
    [
        ("province_code", "withholding.province_digits"),
        ("naturaleza", "withholding.naturaleza_digits"),
        ("fecha_inicio_prestamo", "withholding.date_digits"),
        ("fecha_vencimiento_prestamo", "withholding.date_digits"),
        ("fecha_devengo", "withholding.date_digits"),
    ],
)
def test_a_digit_code_of_another_width_than_the_form_declares_is_refused(field: str, key: str) -> None:
    width = _declared(key)
    assert not _refused(PublicAnnualRecipientDetail, field, "1" * width)
    assert _refused(PublicAnnualRecipientDetail, field, "1" * (width - 1))
    assert _refused(PublicAnnualRecipientDetail, field, "1" * (width + 1))
    assert _refused(PublicAnnualRecipientDetail, field, "x" * width)


def test_an_order_number_above_the_declared_ceiling_is_refused() -> None:
    ceiling = _declared("withholding.numero_orden_max")
    assert not _refused(PublicAnnualRecipientDetail, "numero_orden", ceiling)
    assert _refused(PublicAnnualRecipientDetail, "numero_orden", ceiling + 1)
    assert _refused(PublicAnnualRecipientDetail, "numero_orden", 0)


def _declared_max_lengths(model: type[BaseModel]) -> dict[str, int | None]:
    return {
        name: next((item.max_length for item in field.metadata if hasattr(item, "max_length")), None)
        for name, field in model.model_fields.items()
    }


def test_the_public_recipient_detail_declares_the_canonical_observation_fields_and_lengths() -> None:
    assert _declared_max_lengths(PublicAnnualRecipientDetail) == _declared_max_lengths(WithholdingObservation)


@pytest.mark.parametrize("field", ["representative_tax_id", "spouse_or_unit_titular_tax_id", "nif_pagador_anterior"])
def test_a_party_identifier_at_the_canonical_capacity_is_accepted_by_the_public_model(field: str) -> None:
    capacity = _declared_max_lengths(WithholdingObservation)[field]
    assert capacity == 64
    outside = contextvars.Context()
    assert not outside.run(_refused, PublicAnnualRecipientDetail, field, "1" * 64)
    assert outside.run(_refused, PublicAnnualRecipientDetail, field, "1" * 65)
