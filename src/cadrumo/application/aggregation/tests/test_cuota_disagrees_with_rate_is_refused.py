"""A ledger row's cuota must equal base x the dated tipo, within one cent.

The rate is checked against the dated registry table, but a cuota typed
independently of it would otherwise reach the Modelo 303 boxes. The tolerance is
the invoice line's: the cuota may differ from ``base * tipo`` by at most one cent
and no more. Expected values below are worked by hand, not read from the code.

Real-behaviour: real :class:`Transaction` rows through the real classifier. No
mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.transactions.models import Transaction
from ..iva_ledger import IvaLedgerAggregationIssueReason
from .iva_ledger_row_support import aggregate_row, uncategorised_sale_row

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


_PERIOD = Period.from_year_and_code(_YEAR, "4T")
_ON = date(_YEAR, 11, 6)
_REFUSED = [IvaLedgerAggregationIssueReason.CUOTA_DISAGREES_WITH_RATE.value]


def _transaction(row_id: str, *, base: Decimal, iva_rate: Decimal, iva_amount: Decimal) -> Transaction:
    return uncategorised_sale_row(row_id, booked=_ON, base=base, iva_rate=iva_rate, iva_amount=iva_amount)


@pytest.mark.parametrize(
    ("base", "rate", "cuota"),
    [
        # 90.00 x 0.21 = 18.90
        ("90.00", "0.21", "18.90"),
        # Upper and lower edge of the one-cent tolerance around 18.90.
        ("90.00", "0.21", "18.91"),
        ("90.00", "0.21", "18.89"),
        # 1000.00 x 0.10 = 100.00
        ("1000.00", "0.10", "100.00"),
        # 1000.00 x 0.04 = 40.00
        ("1000.00", "0.04", "40.00"),
        ("1000.00", "0", "0"),
    ],
)
def test_a_cuota_within_a_cent_of_base_times_rate_is_admitted(base: str, rate: str, cuota: str) -> None:
    observations, reasons = aggregate_row(
        _transaction("row-ok", base=Decimal(base), iva_rate=Decimal(rate), iva_amount=Decimal(cuota)), _PERIOD
    )
    assert reasons == []
    assert len(observations) == 1
    assert observations[0].base_amount == Decimal(base)
    assert observations[0].iva_amount == Decimal(cuota)


@pytest.mark.parametrize(
    ("base", "rate", "cuota"),
    [
        ("90.00", "0.21", "31.00"),
        # One hundredth beyond the tolerance, on both sides of 18.90.
        ("90.00", "0.21", "18.92"),
        ("90.00", "0.21", "18.88"),
        # A reduced-rate row carrying the general-rate cuota: 1000 x 0.21 = 210.
        ("1000.00", "0.10", "210.00"),
    ],
)
def test_a_cuota_beyond_a_cent_from_base_times_rate_is_refused_and_not_aggregated(
    base: str, rate: str, cuota: str
) -> None:
    observations, reasons = aggregate_row(
        _transaction("row-bad", base=Decimal(base), iva_rate=Decimal(rate), iva_amount=Decimal(cuota)), _PERIOD
    )
    assert observations == ()
    assert reasons == _REFUSED
