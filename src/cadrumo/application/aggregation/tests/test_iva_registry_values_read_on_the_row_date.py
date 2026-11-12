"""A ledger row's stored IVA registry values are judged on its own devengo date.

The cash-accounting treatment, the exemption article and the art. 104.Tres
exclusion are dated vocabularies. Each is read on the date the law selects for
the row -- its operation date, else its ledger filing date -- and never on the
day the program runs. A row dated below the support floor is refused by the
governed-fact gate with the year it was asked about, which a current-date read
could not do; a row whose operation date is inside the envelope is judged there
whatever its bank date says.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from ....core.prorrata_exclusions import Art104TresExclusion
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.iva_category_catalogue import require_iva_category
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.iva.schema import IvaExemptionArticle
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction
from ..iva_ledger_apportionment import _partition_by_input_classification
from ..iva_transaction import (
    _unaccepted_art_104_tres_exclusion_issue,
    _unaccepted_cash_accounting_treatment_issue,
    _unaccepted_exemption_article_issue,
)
from .ledger_transaction_support import iva_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_ENVELOPE = filing_year_envelope()
_INSIDE = date(_ENVELOPE.horizon, 6, 15)
_BELOW_FLOOR = date(_ENVELOPE.floor, 1, 1) - timedelta(days=1)


def _row(*, booked: date, operation_date: date | None) -> Transaction:
    row = iva_transaction(
        "row-date",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        booked_date=booked,
    )
    return row.model_copy(
        update={
            "operation_date": operation_date,
            "exemption_article": IvaExemptionArticle("art_20_uno_8"),
            "art_104_tres_exclusion": Art104TresExclusion("foreign_permanent_establishment"),
        }
    )


def _checks(row: Transaction) -> None:
    with bundled_indexed_authority().operation() as operation:
        _unaccepted_cash_accounting_treatment_issue(row, operation=operation)
        _unaccepted_exemption_article_issue(
            row,
            transaction_id=row.transaction_id,
            effective_category=require_iva_category("domestic_exempt", authority=operation),
            operation=operation,
        )
        _unaccepted_art_104_tres_exclusion_issue(row, transaction_id=row.transaction_id, operation=operation)


def test_a_row_dated_inside_the_envelope_is_judged() -> None:
    _checks(_row(booked=_INSIDE, operation_date=None))


def test_a_row_dated_below_the_floor_is_refused_on_that_year() -> None:
    with pytest.raises(RegistryValidationError, match=str(_BELOW_FLOOR.year)):
        _checks(_row(booked=_BELOW_FLOOR, operation_date=None))


def test_the_operation_date_outranks_the_bank_date() -> None:
    _checks(_row(booked=_BELOW_FLOOR, operation_date=_INSIDE))
    with pytest.raises(RegistryValidationError, match=str(_BELOW_FLOOR.year)):
        _checks(_row(booked=_INSIDE, operation_date=_BELOW_FLOOR))


def test_the_art_106_classifications_are_read_on_the_date_the_revision_names() -> None:
    with bundled_indexed_authority().operation() as operation:
        assert _partition_by_input_classification((), effective_date=_INSIDE, operation=operation)
        with pytest.raises(RegistryValidationError, match=str(_BELOW_FLOOR.year)):
            _partition_by_input_classification((), effective_date=_BELOW_FLOOR, operation=operation)
