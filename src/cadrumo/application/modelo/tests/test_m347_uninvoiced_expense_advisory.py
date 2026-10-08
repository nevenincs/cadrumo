"""The Modelo 347 advisory for business expenses the ledger holds without an invoice.

Modelo 347 relates the invoiced operations, while RD 1065/2007 art. 35.1 also
dates operations by "la factura o documento contable que sirva de justificante".
An outgoing business transaction with a taxable base and no linked invoice is
therefore an operation the declaration cannot see, and the filer is told once
per calculation. The transactions are real :class:`Transaction` models; the
repository double only hands the collector the ejercicio's catalogue and records
the window it asked for.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import LedgerDatePartition, Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...aggregation.source_mesh import CalculationSourceDiagnostic
from .._m347_uninvoiced_expense_advisory import (
    M347_UNINVOICED_EXPENSE_SOURCE_KIND,
    collect_m347_uninvoiced_expense_diagnostics,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_PERIOD = "0A"
_BUCKET_ID = "cd7a6304-2000-4200-8200-000000000348"


class _EjercicioCatalogue:
    """Hand the collector a fixed catalogue and keep the filing-date window it requested.

    Only the windowed read is the collector's to make; every other repository
    operation refuses, so a collector reaching past its window fails the test.
    """

    def __init__(self, transactions: tuple[Transaction, ...]) -> None:
        self._catalogue = TransactionCatalogue.from_transactions(transactions)
        self.windows: list[tuple[date, date]] = []

    @property
    def bucket_id(self) -> str:
        return _BUCKET_ID

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        self.windows.append((start, end))
        return self._catalogue

    def exists(self) -> bool:
        raise AssertionError("the collector reads only the ejercicio window")

    def load(self) -> TransactionCatalogue:
        raise AssertionError("the collector reads only the ejercicio window")

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        raise AssertionError(f"the collector reads only the ejercicio window, not {list(transaction_ids)}")

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        raise AssertionError(f"the collector reads only the ejercicio window, not a partition {start}..{end}")

    def save(self, catalogue: TransactionCatalogue) -> None:
        raise AssertionError(f"the collector never writes ({len(catalogue.transactions)} transactions)")


def _transaction(
    provider_id: str,
    *,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    taxable_base: Decimal | None = Decimal("4000.00"),
    invoice_id: str | None = None,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2025, 6, 10),
        value_date=date(2025, 6, 10),
        amount=Decimal("4840.00"),
        currency="EUR",
        counterparty="PROVEEDOR SIN FACTURA SL",
        description=f"m347 uninvoiced {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2025, 6, 11, 9, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )
    payload: dict[str, object] = {
        "raw": raw,
        "direction": direction,
        "business_classification": business_classification,
        "source_jurisdiction": "ES",
        "group_label": None,
        "lifecycle_state": lifecycle_state,
        "taxable_base": taxable_base,
    }
    if business_pct is not None:
        payload["business_pct"] = business_pct
    if invoice_id is not None:
        payload["invoice_id"] = invoice_id
    return Transaction.model_validate(payload)


def _diagnostics(
    repository: _EjercicioCatalogue,
    *,
    modelo: str = "347",
) -> tuple[CalculationSourceDiagnostic, ...]:
    return collect_m347_uninvoiced_expense_diagnostics(
        modelo=modelo,
        period_token=_PERIOD,
        filing_year=2025,
        transaction_repository=repository,
    )


def test_uninvoiced_business_expenses_are_named_in_one_advisory() -> None:
    first = _transaction("expense-a")
    second = _transaction(
        "expense-b",
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.5"),
    )
    repository = _EjercicioCatalogue((first, second))

    diagnostics = _diagnostics(repository)

    assert len(diagnostics) == 1
    advisory = diagnostics[0]
    assert advisory.reason == "source_issue"
    assert advisory.source_kind == M347_UNINVOICED_EXPENSE_SOURCE_KIND
    assert advisory.asserted_legal_refs == ("rd-1065-2007:art-33", "rd-1065-2007:art-35")
    assert advisory.message.startswith("2 business expenses of ejercicio 2025")
    assert first.transaction_id in advisory.message
    assert second.transaction_id in advisory.message
    assert repository.windows == [(date(2025, 1, 1), date(2025, 12, 31))]


def test_invoiced_personal_incoming_baseless_and_archived_rows_do_not_fire() -> None:
    repository = _EjercicioCatalogue(
        (
            _transaction("invoiced", invoice_id="inv-0001"),
            _transaction("personal", business_classification=BusinessClassification.PERSONAL),
            _transaction("income", direction=TransactionDirection.INCOMING),
            _transaction("no-base", taxable_base=None),
            _transaction("zero-base", taxable_base=Decimal("0")),
            _transaction("archived", lifecycle_state=TransactionLifecycleState.ARCHIVED),
        ),
    )

    assert _diagnostics(repository) == ()


def test_other_modelos_never_read_the_ledger() -> None:
    repository = _EjercicioCatalogue((_transaction("expense-a"),))

    assert _diagnostics(repository, modelo="349") == ()
    assert repository.windows == []
