"""A foreign invoice converts at the rate in force at devengo, not at the rate of its issue date.

LIVA art. 79.Once: "En las operaciones cuya contraprestación se hubiese fijado
en moneda o divisa distintas de las españolas, se aplicará el tipo de cambio
vendedor, fijado por el Banco de España, que esté vigente en el momento del
devengo" (bundled normative ``ley-37-1992.html``). The date the rate is read at
is therefore the art. 75 devengo date, which an invoice records in
``operation_date`` whenever it differs from expedition (RD 1619/2012 art.
6.1.i), and the issue date only stands in where no operation date is recorded.

The divergence is not cosmetic: an invoice issued in April for a service
performed in March is converted at March's rate, and the two rates differ on
every pair of dates the series publishes separately. Taking the issue date
would move the euro base of every invoice whose document postdates its
operation, which is the ordinary case rather than an edge one.

The rates here are synthetic and published by the same deterministic rate
capability the other FX tests in this package drive the real builder with; the
real ECB adapter is covered at its own seam.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.currency.models import EurRateLookup
from ....domain.currency.service import OPERATOR_DECLARED_RATE_SOURCE
from ....domain.currency.tests.fx_lookup import eur_rate_lookup
from ....domain.invoices.models import Invoice
from ....domain.iva.schema import InvoiceKind
from ..catalogue_creation import build_catalogue_invoice
from ..catalogue_creation_ports import CatalogueInvoiceRateProviderPort

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "4d4d4d4d-4d4d-4d4d-8d4d-4d4d4d4d4d4d"
_PROVIDER_SOURCE = "deterministic-test"
_BASE = Decimal("1000.00")
_DEVENGO_RATE = Decimal("0.910000000")
_ISSUE_RATE = Decimal("0.950000000")
_DECLARED_RATE = Decimal("0.9250")


def _devengo_date() -> date:
    """The date the operation was performed, in the month before the document."""
    return date(filing_year_envelope().horizon, 3, 10)


def _issue_date() -> date:
    """The date the document was expedited, in the month after the operation."""
    return date(filing_year_envelope().horizon, 4, 7)


class _TwoDateRateProvider:
    """Publishes a different USD rate on each of the two dates, and none elsewhere."""

    @property
    def rate_source_id(self) -> str:
        return _PROVIDER_SOURCE

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        return eur_rate_lookup(self._rate(currency, rate_date), rate_date=rate_date, source=self.rate_source_id)

    def _rate(self, currency: str, rate_date: date) -> Decimal | None:
        if currency != "USD":
            return None
        if rate_date == _devengo_date():
            return _DEVENGO_RATE
        if rate_date == _issue_date():
            return _ISSUE_RATE
        return None


def _invoice(
    *,
    provider: CatalogueInvoiceRateProviderPort,
    issued_at: date,
    operation_date: date | None,
    declared_fx_rate: Decimal | None = None,
    number: str = "US-0051",
) -> Invoice:
    return build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Überseehandel GmbH",
        counterparty_tax_id="DE811907980",
        counterparty_country="DE",
        invoice_number=number,
        issued_at=issued_at,
        operation_date=operation_date,
        taxable_base=_BASE,
        iva_rate=None,
        currency="USD",
        declared_fx_rate=declared_fx_rate,
        rate_provider=provider,
    )


def test_the_published_rate_is_read_at_the_operation_date_not_at_the_issue_date() -> None:
    """The defect this module exists for: an April document for a March operation.

    Both dates publish a rate, so reading the wrong one produces a plausible
    euro base rather than a visible gap. The amount is asserted, not just the
    stamp date: a stamp naming the devengo date while carrying the issue date's
    rate would be worse than either, since the provenance would then
    misdescribe the figure.
    """
    invoice = _invoice(provider=_TwoDateRateProvider(), issued_at=_issue_date(), operation_date=_devengo_date())

    assert invoice.operation_date == _devengo_date()
    assert invoice.issued_at == _issue_date()
    assert invoice.fx_rate == _DEVENGO_RATE, "LIVA art. 79.Once reads the rate in force at the devengo"
    assert invoice.fx_rate_date == _devengo_date()
    assert invoice.fx_rate_observation_date == _devengo_date(), "the stamp must name the publication it read"
    assert invoice.fx_rate_source == _PROVIDER_SOURCE
    assert invoice.base_total_eur == (_BASE * _DEVENGO_RATE).quantize(Decimal("0.01"))
    assert invoice.base_total_eur != (_BASE * _ISSUE_RATE).quantize(Decimal("0.01"))


def test_an_invoice_recording_no_operation_date_still_converts_at_its_issue_date() -> None:
    """The control: with no recorded devengo the issue date is the substitute, as before."""
    invoice = _invoice(provider=_TwoDateRateProvider(), issued_at=_issue_date(), operation_date=None)

    assert invoice.operation_date is None
    assert invoice.fx_rate == _ISSUE_RATE
    assert invoice.fx_rate_date == _issue_date()


def test_an_operation_invoiced_on_its_own_date_is_unchanged() -> None:
    """The second control: where the two dates agree, nothing about the stamp moves."""
    invoice = _invoice(provider=_TwoDateRateProvider(), issued_at=_devengo_date(), operation_date=_devengo_date())

    assert invoice.fx_rate == _DEVENGO_RATE
    assert invoice.fx_rate_date == _devengo_date()


def test_a_declared_rate_is_stamped_with_the_devengo_date_it_applies_to() -> None:
    """The operator's statement is of the rate in force at devengo, so the stamp says that date.

    The amount is the operator's and must not move; what the stamp records is
    which date the statement answers for, and art. 79.Once makes that the
    devengo date rather than the expedition date.
    """
    invoice = _invoice(
        provider=_TwoDateRateProvider(),
        issued_at=_issue_date(),
        operation_date=_devengo_date(),
        declared_fx_rate=_DECLARED_RATE,
    )

    assert invoice.fx_rate == _DECLARED_RATE, "a declared rate is never replaced by a published one"
    assert invoice.fx_rate_source == OPERATOR_DECLARED_RATE_SOURCE
    assert invoice.fx_rate_observation_date is None, "no publication was read for a declared rate"
    assert invoice.fx_rate_date == _devengo_date()
