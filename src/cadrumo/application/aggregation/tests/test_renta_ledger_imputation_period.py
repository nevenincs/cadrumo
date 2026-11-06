"""Activity income, expense and withholding credit boxes follow the dated imputation criterion.

LIRPF art. 14.1.b imputes activity income on accrual and RIRPF art. 7.2 opens a
cash election. An invoice accrued on 20 December and collected on 10 January
therefore belongs to the earlier ejercicio unless the taxpayer elected cash; the
ledger places it in the later one on its bank date only under the cash election.
Every case runs the production resolver against the published revision.

Worked figures: 1.000,00 base + 210,00 IVA - 150,00 retencion = 1.060,00 banked.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.aggregation import BindingValueOutcome
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_grade_cap_reach import capped_binding_reach, snapshot_reach_date
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind, IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.transactions.service import link_invoice
from ...actividad_asset.tests.register_support import MemoryRepository
from ..modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .ledger_source_mesh_support import InMemoryTransactionCatalogueRepository
from .renta_income_aggregation_support import catalogue_read_ports, renta_income_aggregation_period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "c4f1a2b3-5d6e-4f70-8a91-b2c3d4e5f608"
_LATER = newest_authored_edition("100")
_EARLIER = _LATER - 1
_ACCRUED = date(_EARLIER, 12, 20)
_COLLECTED = date(_LATER, 1, 10)
_BASE = Decimal("1000.00")
_IVA = Decimal("210.00")
_RETENCION = Decimal("150.00")
_BANKED = Decimal("1060.00")
_INCOME_0171 = "renta-ledger-income-0171"
_CREDIT_0599 = "renta-ledger-actividad-retenciones-0599"


def _receipt(on: date) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=f"cobro-{on.isoformat()}",
                booked_date=on,
                value_date=on,
                amount=_BANKED,
                currency="EUR",
                counterparty="Cliente SL",
                description="cobro factura",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="e" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(_LATER, 2, 1, 12, 0, tzinfo=UTC),
                    provider_name="CSV provider",
                ),
                raw_fields={},
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": "actividad_economica",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_LATER, 2, 1, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _issued(*, linked: tuple[str, ...], status: PaymentStatus) -> Invoice:
    line = InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=_IVA,
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "F-1",
            "issued_at": _ACCRUED,
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "bucket_id": _BUCKET,
            "base_total": _BASE,
            "iva_total": _IVA,
            "grand_total": _BASE + _IVA,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": status,
            "iva_category": IvaCategory("domestic_general"),
            "retention_rate": Decimal("0.15"),
            "retention_amount": _RETENCION,
            "linked_transaction_ids": linked,
        },
    )


def _boundary_ledger() -> tuple[TransactionCatalogue, InvoiceCatalogue]:
    receipt = _receipt(_COLLECTED)
    invoice = _issued(linked=(receipt.transaction_id,), status=PaymentStatus.PAID)
    catalogue = link_invoice(
        TransactionCatalogue.from_transactions((receipt,)), receipt.transaction_id, invoice.invoice_id
    )
    return catalogue, build_invoice_catalogue((invoice,))


def _resolve(
    transactions: TransactionCatalogue, invoices: InvoiceCatalogue, *, year: int
) -> CalculationSourceResolution:
    repository = InMemoryTransactionCatalogueRepository(bucket_id=_BUCKET)
    repository.save(transactions)
    resolver = LedgerRentaIncomeAggregationSourceResolver(
        activity_asset_history_repository=MemoryRepository(),
        transaction_repository=repository,
        ports=catalogue_read_ports(invoices=invoices, transactions=transactions),
    )
    return resolver.resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET,
            modelo="100",
            filing_year=year,
            period=renta_income_aggregation_period(year, "0A"),
            revision=published_snapshot("100", filing_year=year, period="0A").revision,
        ),
    )


def test_an_unset_criterion_places_no_income_and_names_the_gap() -> None:
    """With no criterion declared the invoice is in neither ejercicio, and both years say the box is unresolved."""
    transactions, invoices = _boundary_ledger()
    earlier = _resolve(transactions, invoices, year=_EARLIER)
    later = _resolve(transactions, invoices, year=_LATER)
    assert earlier.binding_values[_INCOME_0171] == Decimal("0")
    assert later.binding_values[_INCOME_0171] == Decimal("0")
    for resolution in (earlier, later):
        assert _INCOME_0171 in {
            str(item.binding_id) for item in resolution.diagnostics if item.reason == "unresolved_binding"
        }


def test_a_zero_beside_an_invoice_accruing_in_the_year_is_not_proven() -> None:
    """The earlier year reads zero only because the money arrived later, for income and its withholding alike."""
    transactions, invoices = _boundary_ledger()
    earlier = _resolve(transactions, invoices, year=_EARLIER)
    assert earlier.value_outcomes[_INCOME_0171] is BindingValueOutcome.FROM_BEARING_ROWS
    assert earlier.value_outcomes[_CREDIT_0599] is BindingValueOutcome.FROM_BEARING_ROWS


def test_a_year_with_no_row_and_no_accruing_invoice_proves_its_zeros() -> None:
    resolution = _resolve(TransactionCatalogue.from_transactions(()), build_invoice_catalogue(()), year=_LATER)
    assert resolution.binding_values[_INCOME_0171] == Decimal("0")
    assert resolution.value_outcomes[_INCOME_0171] is BindingValueOutcome.PROVEN_ZERO
    assert resolution.value_outcomes[_CREDIT_0599] is BindingValueOutcome.PROVEN_ZERO


@pytest.mark.parametrize(("modelo", "period"), [("100", "0A"), ("130", "1T")])
def test_no_ledger_box_stays_capped(operation: PinnedAuthorityOperation, modelo: str, period: str) -> None:
    """Income, expense and withholding credit boxes all read the dated criterion, so none is capped."""
    snapshot = operation.snapshot(modelo, filing_year=_LATER, period=period)
    assert not capped_binding_reach(
        snapshot.revision, authority=operation, effective_date=snapshot_reach_date(snapshot)
    )


def test_the_register_owned_amortization_boxes_stay_uncapped(operation: PinnedAuthorityOperation) -> None:
    """Boxes 0208 and 0227 read the asset register's dated schedule, not a bank row."""
    snapshot = operation.snapshot("100", filing_year=_LATER, period="0A")
    reach = capped_binding_reach(snapshot.revision, authority=operation, effective_date=snapshot_reach_date(snapshot))
    assert "renta-ledger-expense-0208-deductible" not in reach
    assert "renta-ledger-expense-0227-deductible" not in reach
