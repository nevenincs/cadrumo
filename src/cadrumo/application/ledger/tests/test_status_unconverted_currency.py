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

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.transactions.classification_effects import fields_refused_by_classification
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.usage_ratios.model import UsageRatioProfile
from ..action_ports import LedgerActionPorts
from ..manual_read import summarize_manual_transactions
from .action_port_fakes import (
    EmptyCalculationRepository,
    EmptyInvoiceRepository,
    EmptyWorkUnitRepository,
    InMemoryAttachmentStore,
    InMemoryEventRepository,
    empty_usage_ratio_profile,
)
from .in_memory_transaction_repository import InMemoryTransactionRepository
from .iva_transaction_support import iva_transaction

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "fx0f0f0f-0000-4000-8000-00000000fx01"
_IVA_RATE = Decimal("0.21")
_T0 = datetime(_YEAR, 1, 10, 10, 0, tzinfo=UTC)


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


def _summarise(*transactions: Transaction, operation: PinnedAuthorityOperation):
    transaction_repository = InMemoryTransactionRepository(
        bucket_id=_BUCKET,
        catalogue=TransactionCatalogue.from_transactions(transactions),
        permit_secure_object_writes=True,
    )
    ports = LedgerActionPorts(
        operation=operation,
        transaction_repository=transaction_repository,
        bucket_event_repository=InMemoryEventRepository(),
        invoice_repository=EmptyInvoiceRepository(bucket_id=_BUCKET),
        attachment_store=InMemoryAttachmentStore(),
        usage_ratio_profile=UsageRatioProfile(),
        usage_ratio_profile_loader=empty_usage_ratio_profile,
        work_unit_repository=EmptyWorkUnitRepository(bucket_id=_BUCKET),
        calculation_repository=EmptyCalculationRepository(bucket_id=_BUCKET),
        purchase_invoice_evidence_records=(),
    )
    return summarize_manual_transactions(
        bucket_id=_BUCKET,
        ports=ports,
    )


def test_a_domestic_row_without_an_explicit_eur_value_is_still_counted(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The fallback is correct here: a EUR row's native amount IS euros.

    Without this the fix would read as a pass merely because everything was
    excluded.
    """
    report = _summarise(_eur_income("fx-domestic", base=Decimal("1000.00")), operation=authority_operation)

    assert report.unconverted_currency_count == 0
    assert Decimal(report.business_income_total) == Decimal("1210.00")


def test_an_unconverted_foreign_row_is_excluded_from_the_total_and_counted(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The defect: its native amount is not euros, so it has nothing to add."""
    domestic = _eur_income("fx-domestic", base=Decimal("1000.00"))
    unconverted = _foreign(_eur_income("fx-foreign", base=Decimal("5000.00")), currency="USD")

    report = _summarise(domestic, unconverted, operation=authority_operation)

    assert report.unconverted_currency_count == 1
    # The domestic row's gross alone -- the foreign figure is absent, not added.
    assert Decimal(report.business_income_total) == Decimal("1210.00")


def test_a_converted_foreign_row_contributes_its_euro_value_not_its_face_value(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Conversion is what makes a foreign row summable, and at the converted figure."""
    # 6050.00 gross at 0.9 -> 5445.00, which is NOT the 6050.00 face value.
    converted = _foreign(
        _eur_income("fx-foreign", base=Decimal("5000.00")),
        currency="USD",
        fx_rate=Decimal("0.9"),
    )

    report = _summarise(converted, operation=authority_operation)

    assert report.unconverted_currency_count == 0
    assert Decimal(report.business_income_total) == Decimal("5445.00")
    assert Decimal(report.business_income_total) != converted.raw.amount


def test_the_count_reports_only_rows_the_roll_up_would_otherwise_have_taken(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """An excluded-anyway row is not an unconverted-currency problem to report.

    A personal row never entered the total, so counting it would send the
    operator to convert a row whose conversion would change nothing.
    """
    personal_foreign = _foreign(
        _eur_income("fx-personal", base=Decimal("5000.00")),
        currency="USD",
    ).model_copy(
        update={
            "business_classification": BusinessClassification.PERSONAL,
            **dict.fromkeys(fields_refused_by_classification(BusinessClassification.PERSONAL)),
        }
    )

    report = _summarise(personal_foreign, operation=authority_operation)

    assert report.unconverted_currency_count == 0
    assert Decimal(report.business_income_total) == Decimal("0.00")
