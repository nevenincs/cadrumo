"""EU VAT-ID validation tests for business operation invoices."""

from __future__ import annotations

import pytest

from .._business_operation_invoice import BusinessOperationInvoiceInputError, validate_eu_iva_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_VALID_EU_IVA_IDS = (
    ("DE345678901", "DE345678901"),
    ("FR12345678901", "FR12345678901"),
    ("FRAB123456789", "FRAB123456789"),
    ("IT12345678901", "IT12345678901"),
    ("IE1234567A", "IE1234567A"),
    ("NL123456789B01", "NL123456789B01"),
    ("ESB12345678", "ESB12345678"),
    ("EL123456789", "EL123456789"),
    ("XI123456789", "XI123456789"),
    ("DE 345 678 901", "DE345678901"),
    ("de345678901", "DE345678901"),
)

_INVALID_EU_IVA_IDS = (
    ("DE12345", "DE"),
    ("DE34567890A", "DE"),
    ("IT1234567890", "IT"),
    ("IE12345678", "IE"),
    ("NL12345678901", "NL"),
    ("GB123456789", "GB"),
    ("DE", None),
    ("DE3456789012", None),
)


@pytest.mark.parametrize(("raw", "expected"), _VALID_EU_IVA_IDS)
def test_valid_eu_iva_id_normalises_to_canonical_form(raw: str, expected: str) -> None:
    assert validate_eu_iva_id(raw) == expected


@pytest.mark.parametrize(("raw", "message_fragment"), _INVALID_EU_IVA_IDS)
def test_invalid_eu_iva_id_is_rejected(raw: str, message_fragment: str | None) -> None:
    if message_fragment is None:
        with pytest.raises(BusinessOperationInvoiceInputError):
            validate_eu_iva_id(raw)
        return

    with pytest.raises(BusinessOperationInvoiceInputError, match=message_fragment):
        validate_eu_iva_id(raw)
