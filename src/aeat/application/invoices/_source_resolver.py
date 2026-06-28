"""Source-mesh resolver for the governed invoice catalogue.

:class:`InvoiceCatalogueSourceResolver` loads the catalogue from the
active bucket through :class:`InvoiceCatalogueRepository` and projects
scalar invoice-source binding values for the calculation mesh.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...adapters.persistence.storage.errors import (
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
    StorageValidationError,
)
from ...core import BindingSourceKind, Period
from ...core.hashing import sha256_hex
from ...domain.calculations.registry import (
    BindingId,
    InvoiceObservation,
    RegistryValidationError,
    resolve_invoice_binding_row_values,
    resolve_invoice_binding_values,
)
from ...domain.invoices import Invoice, InvoiceCatalogueRepository
from ...domain.invoices._protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.iva import InvoiceKind, IvaCategory
from ...domain.modelos import Modelo349OperadorRow, validate_m349_country_prefix_context
from ..aggregation._source_mesh import (
    CalculationSourceContext,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    storage_degradation_resolution,
)
from ..ledger import (
    BusinessOperationInvoice,
    BusinessOperationInvoiceDirection,
    BusinessOperationInvoiceRepository,
    IntracomOperationType,
)

_OWNED_SOURCES: tuple[BindingSourceKind, ...] = (
    BindingSourceKind.COLLECTIBLE_INVOICE,
    BindingSourceKind.PAYABLE_INVOICE,
)
_STORAGE_DEGRADATION_ERRORS = (ClassificationError, DecryptionError, EnvelopeVersionError)
_M349_PAYABLE_SUMMARY_BINDING_MIRRORS: dict[str, str] = {
    "iva-349-declarante-numero-operadores-adquisicion": "iva-349-declarante-numero-operadores",
    "iva-349-declarante-importe-operaciones-adquisicion": "iva-349-declarante-importe-operaciones",
    "iva-349-declarante-numero-rectificaciones-adquisicion": "iva-349-declarante-numero-rectificaciones",
    "iva-349-declarante-importe-rectificaciones-adquisicion": "iva-349-declarante-importe-rectificaciones",
}
_M349_OPERADOR_ROW_BINDINGS: dict[BindingId, str] = {
    "iva-349-operador-row-codigo-pais": "codigo_pais",
    "iva-349-operador-row-nif": "nif_comunitario",
    "iva-349-operador-row-apellidos": "razon_social",
    "iva-349-operador-row-clave": "clave_operacion",
    "iva-349-operador-row-base": "importe",
}


def invoice_direction_to_source_kind(kind: InvoiceKind) -> BusinessOperationInvoiceDirection:
    """Map an invoice direction to its settlement source kind.

    The single contractual home for the direction↔settlement relationship,
    consumed by both :class:`InvoiceCatalogueSourceResolver` and the operator
    ``aeat app ledger invoice`` CLI. An *issued* invoice (we billed a customer)
    is *collectible*; a *received* invoice (a vendor billed us) is *payable*.

    Returns:
        The :class:`BusinessOperationInvoiceDirection` settling ``kind``.
    """
    if kind is InvoiceKind.ISSUED:
        return BusinessOperationInvoiceDirection.COLLECTIBLE_INVOICE
    return BusinessOperationInvoiceDirection.PAYABLE_INVOICE


class InvoiceCatalogueSourceResolver:
    """Resolve scalar invoice-source bindings from persisted invoice records."""

    resolver_id = "invoice_catalogue"
    owned_sources = _OWNED_SOURCES

    def __init__(
        self,
        *,
        invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
        business_invoice_repository: BusinessOperationInvoiceRepository | None = None,
    ) -> None:
        self._invoice_repository = invoice_repository
        self._business_invoice_repository = business_invoice_repository

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
        catalogue_observed = tuple(
            (invoice, observation)
            for invoice in source_invoices
            if (observation := _invoice_observation(invoice, context=context)) is not None
        )
        try:
            business_invoices = _load_business_operation_invoices(
                context,
                repository=self._business_invoice_repository,
                rich_invoice_repository=self._invoice_repository,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=tuple(active_sources),
                error=exc,
            )
        business_observed = tuple(
            (invoice, observation)
            for invoice in business_invoices
            if _business_invoice_source_kind(invoice) in active_sources
            if (observation := _business_invoice_observation(invoice, context=context)) is not None
        )
        observations = tuple(observation for _, observation in catalogue_observed) + tuple(
            observation for _, observation in business_observed
        )
        binding_values = resolve_invoice_binding_values(context.revision, observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=_m349_declarante_summary_union(context=context, binding_values=binding_values),
            detail_rows=_m349_operador_rows_from_observations(context=context, observations=observations),
            source_transaction_ids=tuple(
                sorted(
                    {
                        transaction_id
                        for invoice, _ in catalogue_observed
                        for transaction_id in invoice.linked_transaction_ids
                    },
                ),
            ),
            provenance=tuple(_invoice_provenance(invoice, observation) for invoice, observation in catalogue_observed)
            + tuple(_business_invoice_provenance(invoice, observation) for invoice, observation in business_observed),
        )


def _invoice_sources_for_revision(context: CalculationSourceContext) -> frozenset[str]:
    return frozenset(binding.source for binding in context.revision.bindings if binding.source in _OWNED_SOURCES)


def _invoice_in_context(invoice: Invoice, context: CalculationSourceContext) -> bool:
    if invoice.bucket_id != context.bucket_id:
        return False
    return _date_in_period(invoice.issued_at, period=context.period)


def _date_in_period(value: date, *, period: Period) -> bool:
    return period.contains(value)


def _invoice_source_kind(invoice: Invoice) -> str:
    return invoice_direction_to_source_kind(invoice.kind).value


def _business_invoice_source_kind(invoice: BusinessOperationInvoice) -> str:
    return invoice.source_kind.value


def _invoice_observation(invoice: Invoice, *, context: CalculationSourceContext) -> InvoiceObservation | None:
    clave = _intracommunity_clave(invoice)
    if clave is None:
        return None
    if str(context.modelo) == "349":
        validate_m349_country_prefix_context(
            country_code=invoice.counterparty_country,
            clave_operacion=clave,
            filing_year=context.filing_year,
            period=context.period.registry_token,
        )
    return InvoiceObservation(
        invoice_id=invoice.invoice_id,
        source_kind=_invoice_source_kind(invoice),
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


def _m349_declarante_summary_union(
    *,
    context: CalculationSourceContext,
    binding_values: dict[str, Decimal],
) -> dict[str, Decimal]:
    if str(context.modelo) != "349":
        return binding_values
    merged = dict(binding_values)
    for payable_binding, public_binding in _M349_PAYABLE_SUMMARY_BINDING_MIRRORS.items():
        if payable_binding not in binding_values:
            continue
        merged[public_binding] = merged.get(public_binding, Decimal("0")) + binding_values[payable_binding]
    return merged


def _m349_operador_rows_from_observations(
    *,
    context: CalculationSourceContext,
    observations: tuple[InvoiceObservation, ...],
) -> tuple[Modelo349OperadorRow, ...]:
    if str(context.modelo) != "349" or not observations:
        return ()
    row_values = resolve_invoice_binding_row_values(context.revision, observations)
    rows: list[Modelo349OperadorRow] = []
    row_indexes = sorted(
        {
            row_index
            for binding_id, row_index in row_values
            if binding_id in _M349_OPERADOR_ROW_BINDINGS
        },
    )
    for row_index in row_indexes:
        values = {
            attr: row_values[(binding_id, row_index)]
            for binding_id, attr in _M349_OPERADOR_ROW_BINDINGS.items()
            if (binding_id, row_index) in row_values
        }
        if set(values) != set(_M349_OPERADOR_ROW_BINDINGS.values()):
            raise RegistryValidationError(f"Modelo 349 invoice row {row_index} is incomplete")
        codigo_pais = values["codigo_pais"]
        nif_comunitario = values["nif_comunitario"]
        razon_social = values["razon_social"]
        clave_operacion = values["clave_operacion"]
        importe = values["importe"]
        if not (
            isinstance(codigo_pais, str)
            and isinstance(nif_comunitario, str)
            and isinstance(razon_social, str)
            and isinstance(clave_operacion, str)
            and isinstance(importe, Decimal)
        ):
            raise RegistryValidationError(f"Modelo 349 invoice row {row_index} has invalid field types")
        try:
            row = Modelo349OperadorRow(
                codigo_pais=codigo_pais,
                nif_comunitario=f"{codigo_pais}{nif_comunitario}",
                razon_social=razon_social,
                clave_operacion=clave_operacion,
                importe=importe,
            )
        except ValueError as exc:
            raise RegistryValidationError(str(exc)) from exc
        rows.append(row)
    return tuple(rows)


def _load_business_operation_invoices(
    context: CalculationSourceContext,
    *,
    repository: BusinessOperationInvoiceRepository | None,
    rich_invoice_repository: InvoiceCatalogueRepositoryProtocol | None,
) -> tuple[BusinessOperationInvoice, ...]:
    try:
        source = repository or BusinessOperationInvoiceRepository(bucket_id=context.bucket_id)
        return tuple(
            record
            for document in source.iter_records()
            if document.bucket_id == context.bucket_id
            for record in document.records
            if _business_invoice_in_context(record, context)
        )
    except StorageValidationError:
        if repository is None and rich_invoice_repository is not None:
            return ()
        raise


def _business_invoice_in_context(invoice: BusinessOperationInvoice, context: CalculationSourceContext) -> bool:
    if invoice.bucket_id != context.bucket_id:
        return False
    return _date_in_period(_business_invoice_date(invoice), period=context.period)


def _business_invoice_observation(
    invoice: BusinessOperationInvoice,
    *,
    context: CalculationSourceContext,
) -> InvoiceObservation | None:
    clave = _business_invoice_clave(invoice)
    if clave is None:
        return None
    country_code = _business_invoice_country_code(invoice)
    party_tax_id = _business_invoice_party_tax_id(invoice)
    if str(context.modelo) == "349":
        validate_m349_country_prefix_context(
            country_code=country_code,
            clave_operacion=clave,
            filing_year=context.filing_year,
            period=context.period.registry_token,
        )
    return InvoiceObservation(
        invoice_id=invoice.invoice_id,
        source_kind=BindingSourceKind(invoice.source_kind.value),
        party_tax_id=party_tax_id,
        country_code=country_code,
        transaction_date=_business_invoice_date(invoice),
        base_amount=invoice.taxable_base,
        intracommunity_clave=clave,
        party_legal_name=invoice.counterparty_name or None,
    )


def _business_invoice_date(invoice: BusinessOperationInvoice) -> date:
    try:
        return date.fromisoformat(invoice.invoice_date)
    except ValueError as exc:
        raise RegistryValidationError(
            f"business invoice {invoice.invoice_id!r} has invalid invoice_date {invoice.invoice_date!r}",
        ) from exc


def _business_invoice_clave(invoice: BusinessOperationInvoice) -> str | None:
    operation_type = invoice.operation_type
    if operation_type is None:
        return None
    if operation_type is IntracomOperationType.R:
        raise RegistryValidationError(
            f"business invoice {invoice.invoice_id!r} uses rectification operation type R "
            "but the slim invoice record has no rectified period/base metadata",
        )
    clave = operation_type.value
    if invoice.source_kind is BusinessOperationInvoiceDirection.COLLECTIBLE_INVOICE and clave in {"A", "I"}:
        raise RegistryValidationError(
            f"business invoice {invoice.invoice_id!r} is issued but uses acquisition operation type {clave!r}",
        )
    if invoice.source_kind is BusinessOperationInvoiceDirection.PAYABLE_INVOICE and clave in {"E", "S"}:
        raise RegistryValidationError(
            f"business invoice {invoice.invoice_id!r} is received but uses supply/service operation type {clave!r}",
        )
    return clave


def _business_invoice_party_tax_id(invoice: BusinessOperationInvoice) -> str:
    value = (invoice.eu_iva_id or invoice.counterparty_nif).strip().upper()
    if not value:
        raise RegistryValidationError(f"business invoice {invoice.invoice_id!r} has no counterparty tax id")
    return value


def _business_invoice_country_code(invoice: BusinessOperationInvoice) -> str:
    if invoice.country_code is not None:
        return invoice.country_code.strip().upper()
    party_tax_id = _business_invoice_party_tax_id(invoice)
    if len(party_tax_id) >= 2 and party_tax_id[:2].isalpha():
        return "GR" if party_tax_id[:2] == "EL" else party_tax_id[:2]
    raise RegistryValidationError(
        f"business invoice {invoice.invoice_id!r} has operation_type but no country_code or EU IVA-ID prefix",
    )


def _invoice_provenance(invoice: Invoice, observation: InvoiceObservation) -> CalculationSourceProvenance:
    payload = observation.model_dump_json()
    source_kind = _invoice_source_kind(invoice)
    return CalculationSourceProvenance(
        source_kind=source_kind,
        source_ref=f"{source_kind}:{observation.invoice_id}",
        fingerprint=f"sha256:{sha256_hex(payload.encode('utf-8'))}",
    )


def _business_invoice_provenance(
    invoice: BusinessOperationInvoice,
    observation: InvoiceObservation,
) -> CalculationSourceProvenance:
    payload = observation.model_dump_json()
    source_kind = _business_invoice_source_kind(invoice)
    return CalculationSourceProvenance(
        source_kind=source_kind,
        source_ref=f"{source_kind}:{observation.invoice_id}",
        fingerprint=f"sha256:{sha256_hex(payload.encode('utf-8'))}",
    )


__all__ = ["InvoiceCatalogueSourceResolver", "invoice_direction_to_source_kind"]
