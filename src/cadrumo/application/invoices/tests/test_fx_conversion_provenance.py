"""A euro figure on a foreign invoice is grounded, or there is no euro figure.

The conversion policy has exactly two outcomes and no third. A rate the
authority actually published produces a euro value stamped with the rate, the
date it was taken at, and the authority that quoted it. A rate that cannot be
resolved produces NO euro value at all -- the record reports ``None`` and is
held back from projection rather than offering its foreign face value.

There is deliberately no default, no ``1``, no "today's rate" for a past
invoice, and no hardcoded literal. Those are the shapes that turn an unknown
into a plausible number, and a plausible number that reaches a filing is worse
than a visible gap: nothing downstream can tell it from a real one.

Both directions of error are covered here, which is not the usual shape in this
tree. The refusal tests watch UNDER-declaration by way of visibility -- an
unconverted invoice leaves the modelo totals, and the operator must be able to
see that it did. The face-value test watches OVER-declaration -- a foreign
amount read as euro overstates the base the taxpayer pays on, and nothing else
in this repository is aimed at that direction.

The rate values used below are ECB euro reference-rate observations, quoted
EUR-base as the ECB publishes them and inverted by the provider under test. The
expected euro figures are derived from those published quotes, never from the
conversion code's own output.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....adapters.outbound.fx._ecb_provider import ECB_RATE_SOURCE_ID, EcbReferenceRateProvider
from ....domain.currency.service import resolve_fx_conversion_stamp
from ....domain.iva.classification import InvoiceKind
from ....tests.ecb_stub import ecb_csv_fetch
from .._creation import build_catalogue_invoice

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "39393939-3939-4939-8939-393939393939"

# Published ECB euro reference rate for 2025-03-14 (EUR-base: 1 EUR = 1.0889 USD).
_QUOTE_DATE = date(2025, 3, 14)
_ECB_USD_QUOTE = Decimal("1.0889")
# The provider inverts an EUR-base quote into the USD -> EUR multiplier.
_EXPECTED_USD_RATE = Decimal("1") / _ECB_USD_QUOTE

_BASE = Decimal("1000.00")


def _rated_provider() -> EcbReferenceRateProvider:
    """A real provider over a stubbed transport: the inversion is exercised.

    The real :class:`EcbReferenceRateProvider` rather than a hand-rolled double,
    so the EUR-base-to-multiplier inversion and the source identity are the
    production ones. Only the HTTP transport is replaced, which is what keeps
    the suite off the network without replacing the logic under test.
    """
    return EcbReferenceRateProvider(fetch=ecb_csv_fetch({"USD": {_QUOTE_DATE: _ECB_USD_QUOTE}}))


def _invoice(*, currency: str, provider):
    return build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Überseehandel GmbH",
        counterparty_tax_id="DE811907980",
        counterparty_country="DE",
        invoice_number="OS-2025-0031",
        issued_at=_QUOTE_DATE,
        taxable_base=_BASE,
        iva_rate=None,
        currency=currency,
        rate_provider=provider,
    )


def test_a_rated_conversion_reaches_the_record_with_its_full_provenance() -> None:
    """The positive control: a resolvable rate converts AND says where it came from.

    Without this, every refusal test below would pass just as happily against a
    conversion path that had been broken outright -- "no euro value" is the
    correct answer to an unresolvable rate and the wrong answer to a resolvable
    one, and only this test can tell those apart.
    """
    invoice = _invoice(currency="USD", provider=_rated_provider())

    assert invoice.currency == "USD"
    assert invoice.fx_rate == _EXPECTED_USD_RATE
    assert invoice.fx_rate_date == _QUOTE_DATE, "the rate must be taken at the invoice's own date (Ley 46/1998 art. 36)"
    assert invoice.fx_rate_source == ECB_RATE_SOURCE_ID, (
        "a stored euro figure that cannot name its rate authority cannot be audited"
    )
    assert invoice.base_total_eur == (_BASE * _EXPECTED_USD_RATE).quantize(Decimal("0.01"))


def test_an_unresolvable_rate_leaves_the_record_unconverted_rather_than_guessed() -> None:
    """No rate means no euro value, and no stamp claiming otherwise.

    A currency the authority publishes no series for. The record must carry its
    foreign figures and say plainly that it has no euro equivalent.
    """
    invoice = _invoice(currency="XYZ", provider=_rated_provider())

    assert invoice.currency == "XYZ"
    assert invoice.fx_rate is None
    assert invoice.fx_rate_date is None
    assert invoice.fx_rate_source is None
    assert invoice.base_total_eur is None, "an unresolvable rate produced a euro figure; something invented one"


def test_an_unconverted_record_never_reports_its_face_value_as_euro() -> None:
    """The over-declaration direction, stated as an amount rather than a shape.

    Returning the face value would declare 1000 foreign units as 1000 euro. For
    a currency worth less than the euro that overstates the base the taxpayer is
    assessed on, and no gate in this tree watches that direction.
    """
    invoice = _invoice(currency="XYZ", provider=_rated_provider())

    assert invoice.base_total == _BASE
    assert invoice.base_total_eur is not _BASE
    assert invoice.base_total_eur is None
    assert invoice.grand_total_eur is None


def test_a_euro_invoice_is_left_unstamped_and_converts_to_itself() -> None:
    """Nothing was converted, so nothing claims to have been.

    A ``1``-valued stamp would assert a conversion that never happened, and
    would make a euro record indistinguishable from a foreign one that happened
    to be quoted at parity.
    """
    invoice = _invoice(currency="EUR", provider=_rated_provider())

    assert invoice.fx_rate is None
    assert invoice.fx_rate_date is None
    assert invoice.fx_rate_source is None
    assert invoice.base_total_eur == _BASE


def test_the_stamp_is_taken_at_the_invoice_date_not_at_a_later_one() -> None:
    """A past invoice is converted at ITS date, never at whatever today is.

    Asked for a date the stubbed series does not publish, the resolver must
    return nothing rather than reaching forward to a date that does. Converting
    at read time would make a stored euro figure drift every time it was read.
    """
    provider = _rated_provider()
    later = date(2025, 6, 30)

    stamp = resolve_fx_conversion_stamp(currency="USD", on_date=later, rate_provider=provider)

    assert stamp is None or stamp.rate_date == later, "the stamp must never carry a date other than the one asked for"


@pytest.mark.parametrize("missing", ["fx_rate_date", "fx_rate_source"])
def test_a_half_written_stamp_is_refused_at_construction(missing: str) -> None:
    """The mutation proof: remove either companion and the record must refuse.

    A rate without its date cannot be located in a published series; a rate
    without its source does not say whose series to look in. Either alone is a
    euro figure wearing the appearance of provenance, which is the state this
    invariant exists to make unrepresentable.
    """
    invoice = _invoice(currency="USD", provider=_rated_provider())
    payload = invoice.model_dump()
    payload[missing] = None

    # The model validator raises ``InvoiceValidationError``; pydantic wraps a
    # validator's exception, so the type crossing the boundary is pydantic's.
    with pytest.raises(ValidationError, match="set together"):
        type(invoice).model_validate(payload)
