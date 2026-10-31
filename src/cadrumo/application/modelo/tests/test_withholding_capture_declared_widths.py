"""The annual-recipient wire model keeps the widths and ceiling the registry declares for the form."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pydantic import BaseModel, ValidationError

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.form_codes import resolve_form_codes
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
