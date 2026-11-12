"""A dated invoice vocabulary is never read on the day the program runs.

The enum fields of an invoice payload are projected from vocabularies the
registry dates. With no issue date to read them on, the dated fields are refused
rather than resolved against a different legal moment, while an undated token
(a transaction kind) still normalises.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..errors import InvoiceValidationError
from ..payload_normalisation import normalise_invoice_enum_fields

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_ISSUED_AT = date(filing_year_envelope().horizon, 6, 15)


def test_a_dated_vocabulary_field_without_an_issue_date_is_refused() -> None:
    with pytest.raises(InvoiceValidationError):
        normalise_invoice_enum_fields({"iva_category": "domestic_general"})


def test_the_same_field_is_read_on_the_issue_date_when_one_is_stated() -> None:
    payload = normalise_invoice_enum_fields({"iva_category": "domestic_general", "issued_at": _ISSUED_AT})

    assert str(payload["iva_category"]) == "domestic_general"
