"""Source-mesh resolver for the governed invoice catalogue.

:class:`InvoiceCatalogueSourceResolver` loads the catalogue from the
active bucket through :class:`InvoiceCatalogueRepository` and projects
scalar invoice-source binding values for the calculation mesh.
"""

from __future__ import annotations

import hashlib
from datetime import date

from ...adapters.persistence.storage.errors import ClassificationError, DecryptionError, EnvelopeVersionError
from ...domain.calculations.registry import InvoiceObservation, resolve_invoice_binding_values
from ...domain.invoices import Invoice, InvoiceCatalogueRepository
from ...domain.invoices._protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.iva import InvoiceKind, IvaCategory
from ..aggregation._source_mesh import (
    CalculationSourceContext,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    storage_degradation_resolution,
)
from ..ledger import BusinessOperationInvoiceSourceKind

_OWNED_SOURCES = ("collectible_invoice", "payable_invoice")
_STORAGE_DEGRADATION_ERRORS = (ClassificationError, DecryptionError, EnvelopeVersionError)


def invoice_direction_to_source_kind(kind: InvoiceKind) -> BusinessOperationInvoiceSourceKind:
    """Map an invoice direction to its settlement source kind.

    The single contractual home for the direction↔settlement relationship,
    consumed by both :class:`InvoiceCatalogueSourceResolver` and the operator
    ``aeat app ledger invoice`` CLI. An *issued* invoice (we billed a customer)
    is *collectible*; a *received* invoice (a vendor billed us) is *payable*.

    Returns:
        The :class:`BusinessOperationInvoiceSourceKind` settling ``kind``.
    """
    if kind is InvoiceKind.ISSUED:
        return BusinessOperationInvoiceSourceKind.COLLECTIBLE_INVOICE
    return BusinessOperationInvoiceSourceKind.PAYABLE_INVOICE


class InvoiceCatalogueSourceResolver:
    """Resolve scalar invoice-source bindings from the encrypted invoice catalogue."""

    resolver_id = "invoice_catalogue"
    owned_sources = _OWNED_SOURCES

    def __init__(self, *, invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None) -> None:
        self._invoice_repository = invoice_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        active_sources = _invoice_sources_for_revision(context)
        if not active_sources:
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)

        repository = self._invoice_repository or InvoiceCatalogueRepository(bucket_id=context.bucket_id)
        try:
            catalogue = repository.load()
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=tuple(active_sources),
                error=exc,
            )
        source_invoices = tuple(
            invoice
            for invoice in catalogue.values()
            if _invoice_in_context(invoice, context) and _invoice_source_kind(invoice) in active_sources
        )
        observed = tuple(
            (invoice, observation)
            for invoice in source_invoices
            if (observation := _invoice_observation(invoice)) is not None
        )
        observations = tuple(observation for _, observation in observed)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_invoice_binding_values(context.revision, observations),
            source_transaction_ids=tuple(
                sorted(
                    {transaction_id for invoice, _ in observed for transaction_id in invoice.linked_transaction_ids},
                ),
            ),
            provenance=tuple(_invoice_provenance(invoice, observation) for invoice, observation in observed),
        )


def _invoice_sources_for_revision(context: CalculationSourceContext) -> frozenset[str]:
    return frozenset(binding.source for binding in context.revision.bindings if binding.source in _OWNED_SOURCES)


def _invoice_in_context(invoice: Invoice, context: CalculationSourceContext) -> bool:
    if invoice.bucket_id != context.bucket_id:
        return False
    return _date_in_period(invoice.issued_at, filing_year=context.filing_year, period=context.period.registry_token)


def _date_in_period(value: date, *, filing_year: int, period: str) -> bool:
    if value.year != filing_year:
        return False
    normalized = period.strip().upper()
    if normalized in {"0A", "A", "ANUAL", "ANNUAL"}:
        return True
    quarter_months = {
        "1T": range(1, 4),
        "Q1": range(1, 4),
        "2T": range(4, 7),
        "Q2": range(4, 7),
        "3T": range(7, 10),
        "Q3": range(7, 10),
        "4T": range(10, 13),
        "Q4": range(10, 13),
    }
    months = quarter_months.get(normalized)
    if months is not None:
        return value.month in months
    return False


def _invoice_source_kind(invoice: Invoice) -> str:
    return invoice_direction_to_source_kind(invoice.kind).value


def _invoice_observation(invoice: Invoice) -> InvoiceObservation | None:
    clave = _intracommunity_clave(invoice)
    if clave is None:
        return None
    return InvoiceObservation(
        invoice_id=invoice.invoice_id,
        party_tax_id=invoice.counterparty_tax_id,
        country_code=invoice.counterparty_country,
        transaction_date=invoice.issued_at,
        base_amount=invoice.base_total,
        intracommunity_clave=clave,
        party_legal_name=invoice.counterparty_name,
    )


def _intracommunity_clave(invoice: Invoice) -> str | None:
    if invoice.iva_category is IvaCategory.INTRA_COMMUNITY_TRIANGULATION:
        return "T"
    if invoice.kind is InvoiceKind.ISSUED and invoice.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY:
        return "E"
    if (
        invoice.kind is InvoiceKind.RECEIVED
        and invoice.iva_category is IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE
    ):
        return "A"
    return None


def _invoice_provenance(invoice: Invoice, observation: InvoiceObservation) -> CalculationSourceProvenance:
    payload = observation.model_dump_json()
    source_kind = _invoice_source_kind(invoice)
    return CalculationSourceProvenance(
        source_kind=source_kind,
        source_ref=f"{source_kind}:{observation.invoice_id}",
        fingerprint=f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}",
    )


__all__ = ["InvoiceCatalogueSourceResolver", "invoice_direction_to_source_kind"]
