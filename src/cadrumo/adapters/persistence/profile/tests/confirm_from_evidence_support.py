"""One-call evidence confirmation for integration tests.

Composes the production prepare and persist steps of the invoice-confirmation
service so tests can confirm a document against real adapters in one call.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from .....application.invoices.catalogue_creation_ports import CatalogueCreationPorts
from .....application.ledger.confirmation_gate import FindingResolution
from .....application.ledger.counterparty_establishment_ports import CounterpartyEstablishmentRepositoryProtocol
from .....application.ledger.evidence_ports import LedgerEvidencePorts
from .....application.ledger.invoice_confirmation import (
    InvoiceConfirmationResult,
    persist_prepared_invoice_confirmation,
    prepare_invoice_confirmation_from_evidence,
)
from .....application.ledger.invoice_confirmation_ports import InvoiceConfirmationPorts
from .....application.ledger.invoice_draft_extraction_ports import InvoiceDraftExtractionPorts
from .....core.aggregation import IntracomOperationType
from .....core.config import Settings
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.invoices.enums import InvoiceClass
from .....domain.iva.classification import InvoiceKind
from .....domain.iva.regime_legend import RegimeLegend
from .....domain.iva.schema import IvaCategory
from .....domain.iva.supply_nature import SupplyNature


def confirm_invoice_draft_from_evidence(
    *,
    bucket_id: str,
    kind: InvoiceKind,
    counterparty_country: str,
    evidence_id: str | None = None,
    attachment_id: str | None = None,
    counterparty_tax_id: str | None = None,
    counterparty_name: str | None = None,
    invoice_number: str | None = None,
    invoice_date: date | None = None,
    taxable_base: Decimal | None = None,
    iva_rate: Decimal | None = None,
    currency: str | None = None,
    iva_amount: Decimal | None = None,
    iva_category: IvaCategory | None = None,
    operation_type: IntracomOperationType | None = None,
    operation_date: date | None = None,
    retention_rate: Decimal | None = None,
    retention_amount: Decimal | None = None,
    recargo_amount: Decimal | None = None,
    invoice_class: InvoiceClass | None = None,
    supply_nature: SupplyNature | None = None,
    series: str | None = None,
    rectifies_invoice_number: str | None = None,
    notes: str = "",
    resolutions: Sequence[FindingResolution] = (),
    confirmed_by: str = "operator",
    settings: Settings | None = None,
    catalogue_creation_ports: CatalogueCreationPorts,
    invoice_confirmation_ports: InvoiceConfirmationPorts,
    counterparty_establishment_repository: CounterpartyEstablishmentRepositoryProtocol,
    evidence_ports: LedgerEvidencePorts,
    extraction_ports: InvoiceDraftExtractionPorts,
    operation: PinnedAuthorityOperation,
    legends: tuple[RegimeLegend, ...],
) -> InvoiceConfirmationResult:
    """Prepare one evidence reference and persist its confirmation in one call.

    Composes the production preparation and persistence steps the runtime
    entrypoints drive separately, so integration tests exercise both against
    real adapters with one invocation.
    """
    prepared = prepare_invoice_confirmation_from_evidence(
        bucket_id=bucket_id,
        kind=kind,
        counterparty_country=counterparty_country,
        evidence_id=evidence_id,
        attachment_id=attachment_id,
        counterparty_tax_id=counterparty_tax_id,
        counterparty_name=counterparty_name,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        taxable_base=taxable_base,
        iva_rate=iva_rate,
        iva_amount=iva_amount,
        currency=currency,
        iva_category=iva_category,
        operation_type=operation_type,
        operation_date=operation_date,
        retention_rate=retention_rate,
        retention_amount=retention_amount,
        recargo_amount=recargo_amount,
        invoice_class=invoice_class,
        supply_nature=supply_nature,
        series=series,
        rectifies_invoice_number=rectifies_invoice_number,
        notes=notes,
        resolutions=resolutions,
        settings=settings,
        catalogue_creation_ports=catalogue_creation_ports,
        counterparty_establishment_repository=counterparty_establishment_repository,
        evidence_ports=evidence_ports,
        extraction_ports=extraction_ports,
        operation=operation,
        legends=legends,
    )
    return persist_prepared_invoice_confirmation(
        prepared,
        confirmed_by=confirmed_by,
        catalogue_creation_ports=catalogue_creation_ports,
        invoice_confirmation_ports=invoice_confirmation_ports,
        evidence_ports=evidence_ports,
    )
