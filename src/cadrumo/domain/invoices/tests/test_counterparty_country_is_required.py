"""The persisted counterparty country must stay required, and why.

The ledger transaction's ``counterparty_country`` is optional, so absence is a
real value elsewhere in the tree. It must not become a real value HERE, because
every consumer that branches on this field branches two ways -- domestic versus
not -- and none can express "the question was not asked". An absent country
would take one of those two branches silently.

The payload normaliser is the specific dependency: when the country is not a
string it forwards the tax id WITHOUT validating it, because it has no country
to validate against. That is safe only while the model then refuses the record
outright. These tests pin both halves together, since the first is harmless
only because of the second.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.identity import IdentityError
from ...iva import InvoiceKind
from .._enums import IvaRate, PaymentStatus
from .._models import Invoice, InvoiceLine, _normalise_invoice_counterparty
from ..errors import InvoiceValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _valid_payload() -> dict[str, object]:
    """A payload the model accepts, so a refusal below can only be the country."""
    line = InvoiceLine.model_validate(
        {
            "description": "Servicios",
            "quantity": Decimal("1"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("100.00"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("21.00"),
        },
    )
    return {
        "kind": InvoiceKind.RECEIVED,
        "invoice_number": "COUNTRY-REQUIRED-001",
        "issued_at": date(2026, 5, 1),
        "counterparty_name": "Papeleria Sol SL",
        "counterparty_tax_id": "A58818501",
        "counterparty_country": "ES",
        "base_total": Decimal("100.00"),
        "iva_total": Decimal("21.00"),
        "grand_total": Decimal("121.00"),
        "currency": "EUR",
        "lines": [line],
        "payment_status": PaymentStatus.PENDING,
    }


def test_the_unmodified_payload_validates() -> None:
    """Anti-tautology control: without it the refusals below prove nothing."""
    assert Invoice.model_validate(_valid_payload()).counterparty_country == "ES"


def test_an_absent_counterparty_country_is_refused_on_that_field() -> None:
    """Absence must refuse, and refuse for the country rather than incidentally."""
    payload = _valid_payload()
    payload["counterparty_country"] = None

    with pytest.raises(ValidationError) as caught:
        Invoice.model_validate(payload)

    failing_fields = {str(error["loc"][0]) for error in caught.value.errors() if error.get("loc")}
    assert "counterparty_country" in failing_fields, caught.value.errors()


def test_the_normaliser_forwards_an_unvalidated_tax_id_when_no_country_is_stated() -> None:
    """Documents the gap the required field closes, so a later reader sees the coupling.

    This is not a defect today. It becomes one the moment the country is
    allowed to be absent on the persisted record, because the tax id would then
    reach storage having been checked against nothing.
    """
    normalised = _normalise_invoice_counterparty(
        {"counterparty_country": None, "counterparty_tax_id": " notavalidnif "},
    )

    assert normalised["counterparty_tax_id"] == "NOTAVALIDNIF"

    # And with a country stated, the same input is held to that country's rules.
    with pytest.raises(IdentityError):  # identity errors vary by country, but all derive from IdentityError
        _normalise_invoice_counterparty(
            {"counterparty_country": "ES", "counterparty_tax_id": " notavalidnif "},
        )


# ── which field, not merely which value ────────────────────────────────────


def test_a_refused_country_names_the_field_it_judged() -> None:
    """The half of the projection row the projection could not deliver.

    The normaliser runs inside a model-level before-mode validator, so pydantic
    has no field location to attach and the error surfaces at ``root`` with the
    exception class and nothing else. The operator-facing projection reports
    that faithfully -- it cannot invent a location the raise site never
    provided. So the fix belongs here, at the one place that still knows which
    field it is judging.
    """
    with pytest.raises(InvoiceValidationError, match="counterparty_country"):
        _normalise_invoice_counterparty({"counterparty_country": "ZZ9"})


def test_a_refused_tax_id_names_the_field_it_judged() -> None:
    """Both identity arms, because they raise from two different hierarchies."""
    with pytest.raises(IdentityError, match="counterparty_tax_id"):
        _normalise_invoice_counterparty({"counterparty_country": "ES", "counterparty_tax_id": "BADID"})

    with pytest.raises(InvoiceValidationError, match="counterparty_tax_id"):
        _normalise_invoice_counterparty({"counterparty_country": "FR", "counterparty_tax_id": "XX"})


def test_naming_the_field_keeps_everything_else_the_error_carried() -> None:
    """The annotation must not cost the structure, which rebuilding it did.

    Rebuilding the exception as ``type(error)(text)`` looks equivalent and is
    not: these errors carry attributes their constructor does not take -- a
    locale key among them -- so a rebuilt instance arrives with a better
    message and no translation key. A shipped assertion on that key caught it,
    which is exactly why the assertion exists, and it is pinned again here so
    the next author reaching for a rebuild is stopped at this file rather than
    two packages away.
    """
    with pytest.raises(IdentityError) as caught:
        _normalise_invoice_counterparty({"counterparty_country": "ES", "counterparty_tax_id": "BADID"})

    assert "must be exactly 9 characters" in str(caught.value), "the value-level reasoning was lost"
    assert caught.value.translated_message == "errors.identity.tax_id_invalid_length", (
        "the translation key did not survive; the exception was rebuilt rather than annotated"
    )
    assert caught.value.context == {"candidate": "BADID", "length": 5}, "the structured context did not survive either"


def test_a_valid_counterparty_passes_through_unwrapped() -> None:
    """Precision: the wrapper must not touch the path that does not refuse."""
    normalised = _normalise_invoice_counterparty(
        {"counterparty_country": "es", "counterparty_tax_id": "b12345674"},
    )

    assert normalised["counterparty_country"] == "ES"
    assert normalised["counterparty_tax_id"] == "B12345674"
