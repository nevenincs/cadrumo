"""Real-behavior tests for the ``gross == taxable_base + iva_amount`` invariant.

The :class:`aeat.domain.transactions.Transaction` model enforces, to the euro
cent, that a populated tax substrate reconstitutes the IVA-inclusive gross —
but only when **both** ``taxable_base`` and ``iva_amount`` are present. Rows
with an unset tax substrate (the common case) must validate unconditionally.

Authority: LLM ledger classification contract.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from .. import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionDirection,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NOW = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)


def _raw(*, amount: Decimal, currency: str = "EUR") -> RawTransaction:
    return RawTransaction(
        transaction_id="row-invariant",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=amount,
        currency=currency,
        counterparty="Contraparte SL",
        description="Compra",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"Concepto": "Compra"},
    )


def test_all_none_tax_substrate_validates() -> None:
    """A row with no tax substrate set must validate (the common case)."""
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("121.00")),
            "direction": TransactionDirection.OUTGOING,
        }
    )
    assert tx.taxable_base is None
    assert tx.iva_amount is None


def test_consistent_triple_validates_against_magnitude_gross() -> None:
    """base + iva == gross magnitude to the cent is accepted (amount is non-negative)."""
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("121.00")),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
        }
    )
    assert tx.taxable_base == Decimal("100.00")
    assert tx.iva_amount == Decimal("21.00")


def test_drifted_triple_is_rejected() -> None:
    """A triple that does not reconstitute the gross raises ValidationError."""
    with pytest.raises(ValidationError, match="must equal the gross to the cent"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("121.00")),
                "direction": TransactionDirection.OUTGOING,
                "business_classification": BusinessClassification.BUSINESS,
                "taxable_base": Decimal("100.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("25.00"),
            }
        )


def test_base_present_but_iva_absent_validates() -> None:
    """The invariant fires only when both fields are present; base-only is fine."""
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("121.00")),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("100.00"),
        }
    )
    assert tx.taxable_base == Decimal("100.00")
    assert tx.iva_amount is None


def test_invariant_uses_native_raw_amount_not_value_in_eur() -> None:
    """For a non-EUR row the gross reference is the native raw.amount.

    The tax substrate (taxable_base / iva_amount) is denominated in the
    row's native currency; the aggregation layer carries value_in_eur as a
    separate parallel EUR projection and does not apply fx_rate to the
    base or amount. So the invariant reconstitutes the native 100.00, not
    the 110.00 EUR conversion.
    """
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("100.00"), currency="USD"),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "fx_rate": Decimal("1.10"),
            "value_in_eur": Decimal("110.00"),
            "rate_source": "ecb_reference",
            "rate_date": "2025-02-10",
            "taxable_base": Decimal("82.64"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("17.36"),
        }
    )
    assert tx.value_in_eur == Decimal("110.00")
    assert tx.taxable_base is not None
    assert tx.iva_amount is not None
    assert tx.taxable_base + tx.iva_amount == Decimal("100.00")


def test_invariant_against_native_amount_rejects_eur_split() -> None:
    """A triple splitting the EUR value (not the native amount) is rejected."""
    with pytest.raises(ValidationError, match="must equal the gross to the cent"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("100.00"), currency="USD"),
                "direction": TransactionDirection.OUTGOING,
                "business_classification": BusinessClassification.BUSINESS,
                "fx_rate": Decimal("1.10"),
                "value_in_eur": Decimal("110.00"),
                "rate_source": "ecb_reference",
                "rate_date": "2025-02-10",
                # Splits the 110.00 EUR value, not the 100.00 native gross.
                "taxable_base": Decimal("90.91"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("19.09"),
            }
        )
