"""Inward FX-conversion eligibility predicates.

The real ECB provider and encrypted transaction-import path live in the
outbound FX integration suite.  These tests keep the aggregation gate's
application-facing behavior independent of those adapters.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.aggregation.currency_predicates import is_non_eur_without_conversion
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.models import Transaction
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_ECB_2024_01_15_USD_RATE = Decimal("1") / Decimal("1.0945")
_USD_AMOUNT = Decimal("100.00")
_EXPECTED_EUR = (_USD_AMOUNT * _ECB_2024_01_15_USD_RATE).quantize(Decimal("0.01"))


def _usd_raw(provider_id: str, *, amount: Decimal = _USD_AMOUNT) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2024, 1, 15),
        value_date=date(2024, 1, 15),
        amount=amount,
        currency="USD",
        counterparty="Acme Corp",
        description=f"USD invoice {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2024, 1, 16, 9, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Reference": provider_id},
    )


def test_usd_transaction_with_value_in_eur_passes_non_eur_predicate() -> None:
    """A USD transaction with value_in_eur is not flagged for conversion."""
    tx = Transaction.model_validate(
        {
            "raw": _usd_raw("usd-gate-001"),
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
            "raw": _usd_raw("usd-gate-002"),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
        },
    )

    assert tx.value_in_eur is None
    assert is_non_eur_without_conversion(tx)
