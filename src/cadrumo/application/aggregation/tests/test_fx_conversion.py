"""Inward FX-conversion eligibility predicates.

The real ECB provider and encrypted transaction-import path live in the
outbound FX integration suite.  These tests keep the aggregation gate's
application-facing behavior independent of those adapters.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.application.aggregation.currency_predicates import is_non_eur_without_conversion
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.models import Transaction

from .fx_conversion_support import USD_AMOUNT, usd_raw

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_ECB_2024_01_15_USD_RATE = Decimal("1") / Decimal("1.0945")
_EXPECTED_EUR = (USD_AMOUNT * _ECB_2024_01_15_USD_RATE).quantize(Decimal("0.01"))


def test_usd_transaction_with_value_in_eur_passes_non_eur_predicate() -> None:
    """A USD transaction with value_in_eur is not flagged for conversion."""
    tx = Transaction.model_validate(
        {
            "raw": usd_raw("usd-gate-001"),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "fx_rate": _ECB_2024_01_15_USD_RATE,
            "value_in_eur": _EXPECTED_EUR,
        },
    )

    assert tx.value_in_eur == _EXPECTED_EUR
    assert not is_non_eur_without_conversion(tx)


def test_usd_transaction_without_conversion_is_flagged() -> None:
    """A USD transaction with no value_in_eur is flagged by the gate predicate."""
    tx = Transaction.model_validate(
        {
            "raw": usd_raw("usd-gate-002"),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
        },
    )

    assert tx.value_in_eur is None
    assert is_non_eur_without_conversion(tx)
