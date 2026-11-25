"""The Modelo 303 recargo casillas declare base x the dated art. 161 rate, never a departing figure.

Each charged row's recargo is weighed against base times the rate LIVA art. 161
pairs with its IVA rate. A row within a cent reaches its rung's casilla as
recorded; a row beyond the cent is refused and reaches no casilla, so the rung
total is the sum of the admitted rows alone. Expected totals are worked by hand:

* general (5.2 %): 1000.00 gives 52.00, and 333.33 gives 17.33316, recorded as
  17.34 (within the cent), so the rung declares 52.00 + 17.34 = 69.34;
* reducido (1.4 %): 2500.00 gives 35.00;
* super-reducido (0.5 %): 1200.00 gives 6.00.

A fourth general-rate sale records 14.00 on a 500.00 base (26.00 expected) and
is refused, so it adds nothing to 69.34.

Real-behaviour: real :class:`Transaction` rows through the real classifier and
the real ``ledger_iva_aggregation`` resolver, against the 303 revision the
published authority selects for each supported year. No mocks, stubs, skips or
xfail.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ..iva_ledger import IvaLedgerAggregationIssueReason
from ..iva_ledger_apportionment import resolve_iva_ledger_binding_values
from .iva_authority_support import aggregate_iva_ledger_observations
from .iva_ledger_row_support import uncategorised_sale_row

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_GENERAL = "modelo-303-recargo-equivalencia-general-cuota"
_REDUCIDO = "modelo-303-recargo-equivalencia-reducido-cuota"
_SUPER_REDUCIDO = "modelo-303-recargo-equivalencia-super-reducido-cuota"

#: (row, base, IVA rate, cuota, recorded recargo)
_ROWS = (
    ("general-exact", "1000.00", "0.21", "210.00", "52.00"),
    ("general-rounded", "333.33", "0.21", "70.00", "17.34"),
    ("general-departing", "500.00", "0.21", "105.00", "14.00"),
    ("reducido", "2500.00", "0.10", "250.00", "35.00"),
    ("super-reducido", "1200.00", "0.04", "48.00", "6.00"),
)


def _sales(on: date) -> tuple[Transaction, ...]:
    return tuple(
        uncategorised_sale_row(
            row_id,
            booked=on,
            base=Decimal(base),
            iva_rate=Decimal(rate),
            iva_amount=Decimal(cuota),
            recargo_amount=Decimal(recargo),
        )
        for row_id, base, rate, cuota, recargo in _ROWS
    )


@pytest.mark.parametrize("year", tuple(filing_year_envelope().years))
def test_each_recargo_casilla_declares_its_admitted_rows_at_the_published_rate(
    year: int, operation: PinnedAuthorityOperation
) -> None:
    on = date(year, 11, 6)
    sales = _sales(on)
    catalogue = TransactionCatalogue.model_validate({"transactions": {row.transaction_id: row for row in sales}})
    aggregation = aggregate_iva_ledger_observations(catalogue, period=Period.from_year_and_code(year, "4T"))
    refused = {issue.transaction_id: issue.reason for issue in aggregation.issues}
    departing = next(row for row in sales if row.raw.provider_transaction_id == "general-departing")
    assert refused == {departing.transaction_id: IvaLedgerAggregationIssueReason.RECARGO_DEPARTS_FROM_PUBLISHED_RATE}

    revision = published_snapshot(Modelo("303"), filing_year=year, period="4T").revision
    values = {
        str(binding_id): value
        for binding_id, value in resolve_iva_ledger_binding_values(
            revision, aggregation.observations, operation=operation
        ).items()
    }
    assert values[_GENERAL] == Decimal("69.34")
    assert values[_REDUCIDO] == Decimal("35.00")
    assert values[_SUPER_REDUCIDO] == Decimal("6.00")
