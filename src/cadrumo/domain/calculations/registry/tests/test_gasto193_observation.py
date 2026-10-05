"""Expense observations enforce their amount invariant at every admission door."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..gasto193_bindings import Gasto193Observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("12.34")])
def test_non_negative_expense_is_admitted(amount: Decimal) -> None:
    observation = Gasto193Observation(
        source_id="expense-row",
        contributor_tax_id="synthetic-id",
        transaction_date=date(2026, 1, 15),
        importe_gastos=amount,
    )
    assert observation.importe_gastos == amount


def test_negative_expense_is_refused_by_construction_and_json_admission() -> None:
    with pytest.raises(ValidationError, match="gasto amounts must be non-negative"):
        Gasto193Observation(
            source_id="expense-row",
            contributor_tax_id="synthetic-id",
            transaction_date=date(2026, 1, 15),
            importe_gastos=Decimal("-0.01"),
        )
    with pytest.raises(ValidationError, match="gasto amounts must be non-negative"):
        Gasto193Observation.model_validate_json(
            '{"source_id":"expense-row","contributor_tax_id":"synthetic-id",'
            '"transaction_date":"2026-01-15","importe_gastos":"-0.01"}'
        )
