"""A foreign row with no conversion is left out of the euro roll-up, and counted.

The money summary added every active business row into one euro total, falling
back to ``raw.amount`` whenever ``value_in_eur`` was absent. For a domestic row
that fallback is right -- its native amount IS euros. For a foreign row that was
never converted it is not an approximation but a different number wearing the
wrong unit: 1000 USD landed in the total as 1000 EUR.

``effective_eur_amount`` already refuses to answer for such a row, and says why:
a caller that skipped the gate must fail loud rather than fold a foreign amount
into a euro-denominated total. The summary was that caller. It now asks the same
shared predicate, excludes the row, and reports how many it excluded, so a
partial total is visible as partial instead of quietly wrong.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind

from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..actions_manual import summarize_manual_transactions

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "fx0f0f0f-0000-4000-8000-00000000fx01"
_IVA_RATE = Decimal("0.21")
_YEAR = 2026
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)


def _raw_transaction(provider_id: str, *, booked_date: date, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        description=f"IVA transaction {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_T0,
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def iva_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    taxable_base: Decimal,
) -> Transaction:
    iva_amount = (taxable_base * _IVA_RATE).quantize(Decimal("0.01"))
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=date(_YEAR, 2, 15),
                amount=taxable_base + iva_amount,
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": "BUSINESS",
            "category_id": "test_iva_operation",
            "taxable_base": taxable_base,
            "iva_rate": _IVA_RATE,
            "iva_amount": iva_amount,
            "deduction_fact_kind": (
                IvaDeductionFactKind._from_registry("domestic_current")
                if direction is TransactionDirection.OUTGOING
                else None
            ),
            "deduction_provenance": (
                IvaDeductionClassificationProvenance(
                    authority=IvaDeductionEvidenceAuthority._from_registry("invoice_evidence"),
                    source_locator=f"test-invoice:{provider_id}",
                    evidence_digest="a" * 64,
                )
                if direction is TransactionDirection.OUTGOING
                else None
            ),
            "classified_at": _T0,
            "classified_by": "manual",
        },
    )


def _eur_income(label: str, *, base: Decimal) -> Transaction:
    return iva_transaction(label, direction=TransactionDirection.INCOMING, taxable_base=base)


def _foreign(
    transaction: Transaction,
    *,
    currency: str,
    fx_rate: Decimal | None = None,
) -> Transaction:
    """Restate a row in a foreign currency, converting it when a rate is given.

    ``fx_rate`` and ``value_in_eur`` must both be set or both be absent, and
    the EUR value is derived from the rate rather than chosen independently:
    the relation is multiplicative over the gross, so an invented pair would
    make the fixture assert a conversion that never happened.
    """
    return transaction.model_copy(
        update={
            "raw": transaction.raw.model_copy(update={"currency": currency}),
            "fx_rate": fx_rate,
            "value_in_eur": None if fx_rate is None else transaction.raw.amount * fx_rate,
        },
    )


def _summarise(*transactions: Transaction):
    return summarize_manual_transactions(
        bucket_id=_BUCKET,
        catalogue=TransactionCatalogue.from_transactions(transactions),
    )


def test_a_domestic_row_without_an_explicit_eur_value_is_still_counted() -> None:
    """The fallback is correct here: a EUR row's native amount IS euros.

    Without this the fix would read as a pass merely because everything was
    excluded.
    """
    report = _summarise(_eur_income("fx-domestic", base=Decimal("1000.00")))

    assert report.unconverted_currency_count == 0
    assert Decimal(report.business_income_total) == Decimal("1210.00")


def test_an_unconverted_foreign_row_is_excluded_from_the_total_and_counted() -> None:
    """The defect: its native amount is not euros, so it has nothing to add."""
    domestic = _eur_income("fx-domestic", base=Decimal("1000.00"))
    unconverted = _foreign(_eur_income("fx-foreign", base=Decimal("5000.00")), currency="USD")

    report = _summarise(domestic, unconverted)

    assert report.unconverted_currency_count == 1
    # The domestic row's gross alone -- the foreign figure is absent, not added.
    assert Decimal(report.business_income_total) == Decimal("1210.00")


def test_a_converted_foreign_row_contributes_its_euro_value_not_its_face_value() -> None:
    """Conversion is what makes a foreign row summable, and at the converted figure."""
    # 6050.00 gross at 0.9 -> 5445.00, which is NOT the 6050.00 face value.
    converted = _foreign(
        _eur_income("fx-foreign", base=Decimal("5000.00")),
        currency="USD",
        fx_rate=Decimal("0.9"),
    )

    report = _summarise(converted)

    assert report.unconverted_currency_count == 0
    assert Decimal(report.business_income_total) == Decimal("5445.00")
    assert Decimal(report.business_income_total) != converted.raw.amount


def test_the_count_reports_only_rows_the_roll_up_would_otherwise_have_taken() -> None:
    """An excluded-anyway row is not an unconverted-currency problem to report.

    A personal row never entered the total, so counting it would send the
    operator to convert a row whose conversion would change nothing.
    """
    personal_foreign = _foreign(
        _eur_income("fx-personal", base=Decimal("5000.00")),
        currency="USD",
    ).model_copy(update={"business_classification": "PERSONAL"})

    report = _summarise(personal_foreign)

    assert report.unconverted_currency_count == 0
    assert Decimal(report.business_income_total) == Decimal("0.00")
