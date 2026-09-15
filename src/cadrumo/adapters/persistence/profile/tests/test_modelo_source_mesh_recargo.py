"""Recargo-equivalencia source-mesh screening contracts for Modelo 303."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

import cadrumo.application.aggregation.modelo_bindings as modelo_bindings
from cadrumo.adapters.persistence.profile.catalogue_reads import InvoiceCatalogueReadAdapter
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.aggregation.errors import AggregationValidationError
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from cadrumo.core.period import Period
from cadrumo.domain.bienes_inversion.register import BienesInversionIvaRegister
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus
from cadrumo.domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from cadrumo.domain.iva.classification import InvoiceKind as CatalogueInvoiceKind
from cadrumo.domain.transactions.models import LedgerDatePartition, TransactionCatalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "28282828-2828-4828-8828-282828282828"


class _EmptyInvoiceCatalogueReader:
    def load(self) -> InvoiceCatalogue:
        return InvoiceCatalogue()


class _EmptyTransactionCatalogueReader:
    def load(self) -> TransactionCatalogue:
        return TransactionCatalogue()

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        return LedgerDatePartition(in_window=TransactionCatalogue(), index_complete=True)


class LedgerIvaAggregationSourceResolver(modelo_bindings.LedgerIvaAggregationSourceResolver):
    """Bind injected real repositories to an explicit empty Bienes authority."""

    def __init__(
        self,
        *,
        transaction_repository: TransactionCatalogueRepository,
        invoice_repository: InvoiceCatalogueRepository | None = None,
    ) -> None:
        super().__init__(
            transaction_repository=transaction_repository,
            invoice_catalogue_read_ports=InvoiceCatalogueReadPorts(
                invoice_reader=(
                    _EmptyInvoiceCatalogueReader()
                    if invoice_repository is None
                    else InvoiceCatalogueReadAdapter(repository=invoice_repository)
                ),
                transaction_reader=_EmptyTransactionCatalogueReader(),
            ),
            prorrata_register_repository=ProrrataRegisterRepository(
                bucket_id=transaction_repository.bucket_id,
            ),
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id=transaction_repository.bucket_id,
        )


@cache
def _m303_revision() -> ModeloRevision:
    return compiled_bundled_authority().snapshot("303", filing_year=2025, period="1T").revision


def _recargo_invoice(invoice_number: str, *, issued_at: date, taxable_base: Decimal) -> Invoice:
    """A repercutido sale to a recargo-regime retailer: cuota plus surcharge."""
    iva_amount = (taxable_base * Decimal("0.21")).quantize(Decimal("0.01"))
    recargo_amount = (taxable_base * Decimal("0.052")).quantize(Decimal("0.01"))
    line = InvoiceLine(
        description="Venta a minorista en recargo",
        quantity=Decimal("1"),
        unit_price=taxable_base,
        subtotal=taxable_base,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=iva_amount,
    )
    return Invoice.model_validate(
        {
            "bucket_id": _BUCKET_ID,
            "kind": CatalogueInvoiceKind.ISSUED,
            "invoice_number": invoice_number,
            "issued_at": issued_at,
            "counterparty_name": "Minorista Recargo SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": taxable_base,
            "iva_total": iva_amount,
            "recargo_amount": recargo_amount,
            "grand_total": taxable_base + iva_amount + recargo_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
        },
    )


def test_the_screen_now_catches_a_recargo_absent_from_the_ledger(
    secure_objects: SecureObjectRepository,
) -> None:
    """A recargo the ledger does not carry is an under-declaration too.

    The screened set covered the four cuota bindings and stopped there, so an
    invoice charging recargo de equivalencia could diverge from the ledger by
    exactly the surcharge and pass. A supplier to a recargo-regime retailer
    charges it ON TOP of the cuota (LIVA art. 161), so the shortfall is real
    money owed, not a presentation detail.

    Extending the screened set alone would have been vacuous: the screen builds
    its observations from LINE metadata, and an invoice's recargo is an
    invoice-level field, so the comparison would have found zero against zero
    and never fired. The surcharge had to be carried onto the observation
    first, through the same canonical bridge the ledger path uses rather than a
    second construction site.
    """
    revision = _m303_revision()
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo.save(
        InvoiceCatalogue.from_invoices(
            (_recargo_invoice("RECARGO-1T", issued_at=date(2025, 2, 10), taxable_base=Decimal("10000.00")),),
        ),
    )

    with pytest.raises(AggregationValidationError) as exc_info:
        LedgerIvaAggregationSourceResolver(
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
        ).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=2025,
                period=Period.from_year_and_code(2025, "1T"),
                revision=revision,
            ),
        )

    context = exc_info.value.context
    assert context is not None, "the refusal must carry its diagnostic context"
    excess = context["invoice_domestic_iva_excess_by_binding"]
    assert isinstance(excess, dict)
    # The recargo tier is named specifically, so the refusal tells the operator
    # which figure is missing rather than only that something is.
    assert "modelo-303-recargo-equivalencia-general-cuota" in excess
