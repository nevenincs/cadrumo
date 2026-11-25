"""Which ledger rows make the Modelo 349 guard refuse a calculation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ...aggregation.tests.ledger_transaction_support import iva_transaction
from ..m349_ledger_guard import is_active_guarded_transaction_in_period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_Q1 = Period.from_year_and_code(filing_year_envelope().horizon, "1T")


@pytest.mark.parametrize(
    ("updates", "guarded"),
    [
        ({}, True),
        (
            {
                "direction": TransactionDirection.INTERNAL_TRANSFER,
                "business_classification": BusinessClassification.PERSONAL,
            },
            False,
        ),
        ({"business_classification": BusinessClassification.PERSONAL}, False),
        ({"business_classification": BusinessClassification.NOT_YET_PROCESSED}, True),
    ],
)
def test_only_a_row_of_the_activity_makes_the_m349_guard_refuse(
    updates: dict[str, object], guarded: bool, *, operation: PinnedAuthorityOperation
) -> None:
    category = IvaCategory("intra_community_acquisition_reverse_charge")
    row = iva_transaction(
        "guarded-row",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("100.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("0.00"),
    ).model_copy(update={"iva_category": category, **updates})
    assert is_active_guarded_transaction_in_period(row, _Q1, frozenset({category})) is guarded
