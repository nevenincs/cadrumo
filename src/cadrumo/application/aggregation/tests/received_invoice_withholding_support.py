"""Synthetic received invoices, paying movements and catalogue readers for withholding tests.

The quarter mirrors APP-QA row 17: a professional bills 300.00 plus 21 per cent
IVA on 28 February with a 15 per cent retención of 45.00, paid net at 318.00
the same day.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.period import Period
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind
from ....domain.transactions.date_partition import LedgerDatePartition
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from ..retenciones import RetencionObservation

NATURAL_PERSON_PROFESSIONAL_NIF = "51234567C"
"""A DNI-form NIF with a valid control letter: an IRPF taxpayer."""

PROFESSIONAL_COMPANY_NIF = "B81000069"
"""A sociedad limitada's NIF: an Impuesto sobre Sociedades taxpayer."""


class EmptyRetencionStore:
    """A per-perceptor retención store holding no row for any window."""

    def load_observations(self, modelo: str, period: Period) -> tuple[RetencionObservation, ...]:
        """Return no stored row."""
        del modelo, period
        return ()

    def load_annual_source_observations(self, source_modelo: str, filing_year: int) -> tuple[RetencionObservation, ...]:
        """Return no stored row."""
        del source_modelo, filing_year
        return ()

    def load_source_observations_through_year(
        self, source_modelo: str, last_filing_year: int
    ) -> tuple[RetencionObservation, ...]:
        """Return no stored row."""
        del source_modelo, last_filing_year
        return ()


class InvoiceReader:
    """Serve one fixed invoice catalogue."""

    def __init__(self, catalogue: InvoiceCatalogue) -> None:
        """Hold ``catalogue``."""
        self._catalogue = catalogue

    def load(self) -> InvoiceCatalogue:
        """Return the held catalogue."""
        return self._catalogue


class MovementReader:
    """Serve one fixed movement catalogue, read whole."""

    def __init__(self, catalogue: TransactionCatalogue) -> None:
        """Hold ``catalogue``."""
        self._catalogue = catalogue

    def load(self) -> TransactionCatalogue:
        """Return the held catalogue."""
        return self._catalogue

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        """Refuse a dated read: the projection reads the whole catalogue."""
        raise AssertionError("the projection reads the whole catalogue")


def invoice_catalogue_ports(invoices: InvoiceCatalogue, movements: TransactionCatalogue) -> InvoiceCatalogueReadPorts:
    """Return catalogue read ports over ``invoices`` and ``movements``."""
    return InvoiceCatalogueReadPorts(
        invoice_reader=InvoiceReader(invoices), transaction_reader=MovementReader(movements)
    )


def paying_movement(provider_id: str, day: date, *, cash: Decimal, irpf_category: str | None) -> Transaction:
    """Return an active outgoing bank movement of ``cash`` on ``day`` with ``irpf_category``."""
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=day,
        value_date=day,
        amount=cash,
        currency="EUR",
        counterparty="Proveedor",
        description=f"TRANSF EMITIDA {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(day.year, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": irpf_category,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(day.year, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def received_invoice(
    number: str,
    day: date,
    *,
    supplier: str,
    tax_id: str,
    base: Decimal,
    retencion: Decimal,
    rate: Decimal,
    linked: tuple[str, ...],
    bucket_id: str | None,
) -> Invoice:
    """Return a received invoice at 21 per cent IVA stating ``retencion`` at ``rate``, with no IVA treatment."""
    cuota = (base * Decimal("0.21")).quantize(Decimal("0.01"))
    line = InvoiceLine(
        description="Servicio",
        quantity=Decimal("1"),
        unit_price=base,
        subtotal=base,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=cuota,
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "invoice_number": number,
            "issued_at": day,
            "counterparty_name": supplier,
            "counterparty_tax_id": tax_id,
            "counterparty_country": "ES",
            "bucket_id": bucket_id,
            "base_total": base,
            "iva_total": cuota,
            "grand_total": base + cuota,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": None,
            "retention_rate": rate,
            "retention_amount": retencion,
            "linked_transaction_ids": linked,
        },
    )


def professional_fee_quarter(
    year: int, *, tax_id: str, irpf_category: str | None, bucket_id: str | None
) -> tuple[InvoiceCatalogue, TransactionCatalogue]:
    """Return row 17's fee for ``year``'s first quarter, billed by ``tax_id`` and paid on ``irpf_category``."""
    fee = paying_movement("GES-PAGO-0228", date(year, 2, 28), cash=Decimal("318.00"), irpf_category=irpf_category)
    invoice = received_invoice(
        f"GES-{year}-001",
        date(year, 2, 28),
        supplier="Pedro Gestor Ejemplo",
        tax_id=tax_id,
        base=Decimal("300.00"),
        retencion=Decimal("45.00"),
        rate=Decimal("0.15"),
        linked=(fee.transaction_id,),
        bucket_id=bucket_id,
    )
    return build_invoice_catalogue((invoice,)), TransactionCatalogue.from_transactions((fee,))
