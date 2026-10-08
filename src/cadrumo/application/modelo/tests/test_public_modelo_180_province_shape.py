"""The public Modelo 180 request admits the same province table as the record it restores."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..invoice_withholding_capture_public import PublicModelo180Address, PublicModelo180Property

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _address(**overrides: str) -> dict[str, str]:
    return {
        "province_code": "28",
        "municipality_code": "079",
        "municipality": "Madrid",
        "locality": "Madrid",
        "postal_code": "28001",
        "street_type": "CL",
        "street_name": "Ejemplo",
        "number_type": "NUM",
        "house_number": "1",
        **overrides,
    }


@pytest.mark.parametrize("province", ["01", "52"])
def test_the_province_table_boundaries_are_admitted(province: str) -> None:
    address = PublicModelo180Address.model_validate(_address(province_code=province, postal_code=f"{province}100"))
    assert address.province_code == province


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("province_code", "00"),
        ("province_code", "53"),
        ("province_code", "99"),
        ("postal_code", "00100"),
        ("postal_code", "53100"),
        ("postal_code", "99999"),
    ],
)
def test_an_address_outside_the_province_table_is_refused(field: str, value: str) -> None:
    with pytest.raises(ValidationError, match=field):
        PublicModelo180Address.model_validate(_address(**{field: value}))


@pytest.mark.parametrize("province", ["00", "53", "99"])
def test_a_recipient_province_outside_the_table_is_refused(province: str) -> None:
    with pytest.raises(ValidationError, match="recipient_province_code"):
        PublicModelo180Property.model_validate(
            {
                "property_key": "p1",
                "situation": "1",
                "cadastral_reference": "1234567AB1234C0001DE",
                "address": _address(),
                "recipient_province_code": province,
                "modality": "1",
                "accrual_year": 2025,
                "withholding_percentage": {"decimal": "19.00"},
            }
        )
