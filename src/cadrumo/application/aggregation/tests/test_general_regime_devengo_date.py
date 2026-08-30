"""Art. 75 devengo attribution for a general-regime ledger row.

Under LIVA art. 75 the cuota is devengada when the operation occurs, whatever
date the money moves. Only the criterio de caja regime (art. 163 terdecies,
opt-in) defers it to collection. Before this contract the devengo date could be
recorded ONLY on a criterio-de-caja row, so a general-regime row -- the one the
law actually binds to the operation date -- had no way to state it and was
attributed to the bank movement date instead. An invoice issued in 1T and paid
in 3T declared its IVA in 3T.

The behaviour is opt-in by design. A row with no operation date keeps filing on
its movement date, which is correct whenever an operation is settled the day it
occurs, and that covers most rows. What changed is that the legally-controlling
date became expressible at all.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from ....core import Period
from ....domain.iva.schema import IvaCashAccountingTreatment, IvaCategory
from ....domain.transactions.dates import transaction_eligible_date_span
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ._iva_authority_support import aggregate_iva_ledger_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PAYMENT = date(2026, 8, 20)
"""3T -- when the bank credit landed."""

_OPERATION = date(2026, 2, 10)
"""1T -- when the invoice was issued, the art. 75 devengo date."""

_CUOTA = Decimal("210.00")


def _raw(provider_id: str) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=_PAYMENT,
        value_date=_PAYMENT,
        amount=Decimal("1210.00"),
        currency="EUR",
        counterparty="Cliente SL",
        description="Cobro factura 2026/007",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="b" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _transaction(provider_id: str, **overrides: Any) -> Transaction:
    payload: dict[str, Any] = {
        "raw": _raw(provider_id),
        "direction": TransactionDirection.INCOMING,
        "business_classification": BusinessClassification.BUSINESS,
        "iva_category": IvaCategory.DOMESTIC_GENERAL,
        "taxable_base": Decimal("1000.00"),
        "iva_amount": _CUOTA,
        "iva_rate": Decimal("0.21"),
        "source_jurisdiction": "ES",
        "group_label": None,
    }
    payload.update(overrides)
    return Transaction(**payload)  # type: ignore[arg-type]


def _cuota_by_quarter(transaction: Transaction) -> dict[str, Decimal]:
    catalogue = TransactionCatalogue.model_validate({transaction.transaction_id: transaction})
    totals: dict[str, Decimal] = {}
    for code in ("1T", "2T", "3T", "4T"):
        aggregation = aggregate_iva_ledger_observations(
            catalogue,
            period=Period.from_year_and_code(2026, code),
        )
        totals[code] = sum(
            (observation.iva_amount or Decimal("0") for observation in aggregation.observations),
            start=Decimal("0"),
        )
    return totals


def test_a_general_regime_row_declares_in_its_devengo_quarter_not_its_payment_quarter() -> None:
    """The defect, inverted: the cuota lands where the operation happened."""
    totals = _cuota_by_quarter(_transaction("tx-devengo", operation_date=_OPERATION))

    assert totals["1T"] == _CUOTA
    assert totals["3T"] == Decimal("0")


def test_a_row_without_an_operation_date_still_files_on_its_movement_date() -> None:
    """The change is opt-in: an unstated devengo date moves nothing.

    Every row that existed before this contract carries no operation date, so
    none of them changes quarter. That is what makes the change safe to land
    on data already recorded.
    """
    totals = _cuota_by_quarter(_transaction("tx-no-devengo"))

    assert totals["3T"] == _CUOTA
    assert totals["1T"] == Decimal("0")


def test_the_cuota_is_declared_exactly_once_across_the_year() -> None:
    """Widening the eligible span must not let one operation declare twice.

    The span now covers both the devengo and the movement date so the period
    partition selects the row from either end, and the aggregator's own date
    gate is what picks the single quarter. If that gate ever stopped
    discriminating, the row would declare in both -- an over-declaration this
    assertion catches and a per-quarter assertion would not.
    """
    totals = _cuota_by_quarter(_transaction("tx-once", operation_date=_OPERATION))

    assert sum(totals.values(), start=Decimal("0")) == _CUOTA
    assert sum(1 for amount in totals.values() if amount) == 1


def test_the_general_regime_may_record_an_operation_date() -> None:
    """The field is no longer gated on criterio de caja.

    This is the structural half of the defect: the regime the law binds to the
    operation date was the one regime forbidden from recording it.
    """
    transaction = _transaction("tx-allowed", operation_date=_OPERATION)

    assert transaction.cash_accounting_treatment is IvaCashAccountingTreatment.NONE
    assert transaction.operation_date == _OPERATION


def test_the_general_regime_still_refuses_cash_accounting_settlement_evidence() -> None:
    """Only the collection series stayed regime-gated, and it must stay so.

    A general-regime operation settles in one movement, so a collection series
    on such a row would describe a regime the taxpayer is not in.
    """
    with pytest.raises(ValidationError, match="requires a non-NONE cash_accounting_treatment"):
        _transaction(
            "tx-evidence",
            cash_accounting_payment_evidence=(
                {
                    "payment_date": _PAYMENT,
                    "taxable_base": Decimal("1000.00"),
                    "iva_amount": _CUOTA,
                },
            ),
        )


def test_the_eligible_span_covers_both_dates_without_the_criterio_de_caja_fallback() -> None:
    """A general-regime span must not stretch to the art. 163 year-end date.

    The period partition selects candidates by span overlap, so the span has to
    reach the devengo date or the row is dropped with no diagnostic. It must
    not reach further: the 31 December year-end fallback is a criterio-de-caja
    construct, and stretching a general-regime row to it would select the row
    into quarters it can never file in.
    """
    span = transaction_eligible_date_span(_transaction("tx-span", operation_date=_OPERATION))

    assert span == (_OPERATION, _PAYMENT)
    assert span[1].year == 2026
