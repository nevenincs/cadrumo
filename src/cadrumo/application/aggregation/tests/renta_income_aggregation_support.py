from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

from dev.registry.compiler.authority import compiled_bundled_authority

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.governed_fact_scope import GovernedFactSource
from ....domain.invoices.models import InvoiceCatalogue
from ....domain.transactions.dates import transaction_eligible_date_span, transaction_filing_date
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.irpf_categories import has_activity_irpf_category, has_employment_irpf_category
from ....domain.transactions.models import (
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
    Transaction,
    TransactionCatalogue,
)
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts


class _InvoiceCatalogueReader:
    """Inward fake for the application invoice projection capability."""

    def __init__(self, catalogue: InvoiceCatalogue) -> None:
        self._catalogue = catalogue

    def load(self) -> InvoiceCatalogue:
        return self._catalogue


class _TransactionCatalogueReader:
    """Inward fake for the application transaction projection capability."""

    def __init__(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue

    def load(self) -> TransactionCatalogue:
        return self._catalogue

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        """Mirror the public date-partition contract over an in-memory catalogue."""
        in_window: list[Transaction] = []
        out_of_window: list[OutOfWindowTransactionIndexEntry] = []
        for transaction in self._catalogue.values():
            earliest, latest = transaction_eligible_date_span(transaction)
            if earliest <= end and latest >= start:
                in_window.append(transaction)
                continue
            out_of_window.append(
                OutOfWindowTransactionIndexEntry(
                    transaction_id=transaction.transaction_id,
                    filing_date=transaction_filing_date(transaction),
                ),
            )
        return LedgerDatePartition(
            in_window=TransactionCatalogue.from_transactions(in_window),
            out_of_window=tuple(out_of_window),
            out_of_window_summary=OutOfWindowTransactionSummary.from_index_entries(out_of_window),
            index_complete=False,
        )


def _catalogue_read_ports(
    *,
    invoices: InvoiceCatalogue,
    transactions: TransactionCatalogue,
) -> InvoiceCatalogueReadPorts:
    """Compose inward fakes for repository-backed aggregation tests."""
    return InvoiceCatalogueReadPorts(
        invoice_reader=_InvoiceCatalogueReader(invoices),
        transaction_reader=_TransactionCatalogueReader(transactions),
    )


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


_ANNUAL_2024 = _period(2024, "0A")
_Q1_2024 = _period(2024, "1T")
_Q2_2024 = _period(2024, "2T")


M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06")
_M100_ACTIVIDAD_ECONOMICA_INGRESOS_CASILLA: CasillaId = validated_casilla_id("0171")
_M130_RETENCIONES_BINDING = "modelo-130-actividad-economica-retenciones-cumulative"
M130_MODELO: str = Modelo("130").value
_M130_ACCEPT_ACTIVITY_MARKER: bool = True


@cache
def _renta_income_category_authority() -> GovernedFactSource:
    """Pin the bundled registry authority used by the category matchers below."""
    return compiled_bundled_authority()


def m130_activity_category_matcher(transaction: Transaction) -> bool:
    """Resolve M130 activity eligibility from the registry-owned taxonomy."""
    return has_activity_irpf_category(
        transaction.irpf_category,
        direction=transaction.direction,
        authority=_renta_income_category_authority(),
    )


def m130_employment_category_matcher(transaction: Transaction) -> bool:
    """Resolve M130 employment exclusion from the registry-owned taxonomy."""
    return has_employment_irpf_category(
        transaction.irpf_category,
        direction=transaction.direction,
        authority=_renta_income_category_authority(),
    )


def raw_transaction(
    provider_id: str,
    *,
    booked_date: date,
    value_date: date | None,
    amount: Decimal = Decimal("1000.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=value_date,
        amount=amount,
        currency=currency,
        counterparty="Cliente SA",
        description=f"income row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2024, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": provider_id},
    )


def _income_transaction(
    provider_id: str,
    *,
    value_date: date,
    amount: Decimal = Decimal("1000.00"),
    currency: str = "EUR",
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": raw_transaction(
                provider_id,
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency=currency,
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": business_classification,
            "business_pct": business_pct,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _actividad_transaction(
    provider_id: str,
    *,
    value_date: date,
    amount: Decimal = Decimal("1000.00"),
    taxable_base: Decimal | None = None,
    iva_rate: Decimal | None = None,
    iva_amount: Decimal | None = None,
    irpf_category: str | None = "actividad_economica",
    business_classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
    business_pct: Decimal | None = None,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": raw_transaction(
                provider_id,
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": business_classification,
            "business_pct": business_pct,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "irpf_category": irpf_category,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _actividad_transaction_with_source(
    provider_id: str,
    *,
    value_date: date,
    amount: Decimal,
    source_jurisdiction: str | None,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": raw_transaction(
                provider_id,
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": "actividad_economica",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
            "source_jurisdiction": source_jurisdiction,
        },
    )
