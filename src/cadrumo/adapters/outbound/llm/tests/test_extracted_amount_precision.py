"""An extracted amount is never silently quantized.

A printed invoice holds amounts to the cent. A reading model's reply can carry
more: a bare JSON number arrives as a binary float, and even a quoted figure
can carry a float's representation error (``145.2000000000000111``). The first
is refused at the parse, because every value is a transcribed string. The
second is a string, so the reader judges its digits: zeros beyond the cent are
only the printed figure written long, and normalize to the cent; any other digit
beyond the cent is one no printed document holds, so the amount is not grounded
and the person is asked for it instead of a rounded guess being recorded.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from .....application.ledger.evidence_errors import PurchaseInvoiceEvidenceReaderError
from .....core.field_origin import FieldOrigin
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..invoice_field_contract import anchor_key_for_field
from ..invoice_field_grounding import ground_extracted_fields, parse_invoice_extraction_response

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _reply_text(taxable_base: str) -> str:
    values = {
        "supplier_tax_id": "B00015016",
        "invoice_number": "F-145",
        "invoice_date": "15/01/1980",
        "taxable_base": taxable_base,
        "iva_rate": "21",
        "currency": "EUR",
    }
    payload = dict(values)
    payload.update({anchor_key_for_field(name): value for name, value in values.items()})
    return json.dumps(payload)


def _grounded_base(taxable_base: str, operation: PinnedAuthorityOperation) -> Decimal | None:
    draft = ground_extracted_fields(
        parse_invoice_extraction_response(_reply_text(taxable_base)),
        raw_text_length=512,
        origin=FieldOrigin.VISION,
        operation=operation,
    )
    return draft.taxable_base


def test_a_bare_long_float_amount_is_refused_as_an_unreadable_answer() -> None:
    reply = _reply_text("145.20").replace('"taxable_base": "145.20"', '"taxable_base": 145.2000000000000111')
    assert '"taxable_base": 145.2000000000000111' in reply

    with pytest.raises(PurchaseInvoiceEvidenceReaderError) as refused:
        parse_invoice_extraction_response(reply)

    assert "unreadable_answer" in str(refused.value.translated_message)


def test_a_quoted_amount_with_a_digit_beyond_the_cent_is_not_grounded(*, operation: PinnedAuthorityOperation) -> None:
    assert _grounded_base("145.2000000000000111", operation) is None


def test_zeros_beyond_the_cent_normalize_to_the_cent(*, operation: PinnedAuthorityOperation) -> None:
    grounded = _grounded_base("145,2000", operation)

    assert grounded == Decimal("145.20")
    assert grounded is not None
    assert grounded.as_tuple().exponent == -2


def test_a_printed_cent_amount_is_kept_as_printed(*, operation: PinnedAuthorityOperation) -> None:
    grounded = _grounded_base("145,20", operation)

    assert grounded is not None
    assert str(grounded) == "145.20"
