"""Compose the existing withholding screen for an admitted installed bucket.

The launcher supplies the active bucket and filing year.  Invoice lookup is a
read of that bucket's encrypted catalogue; all mutations remain in the shared
withholding observation service used by the CLI.
"""

from __future__ import annotations

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ....application.invoices.catalogue_lifecycle import resolve_catalogue_invoice
from ....core.errors.hierarchy import CadrumoError
from ....domain.invoices.errors import InvoiceNotFoundError
from ....domain.invoices.models import Invoice, InvoiceCatalogue
from ...adapter_composition import build_withholding_observation_service
from .door import TuiWithholdingDoor
from .screen import WithholdingEvidenceScreen


def compose_installed_withholding_screen(*, bucket_id: str, filing_year: int) -> WithholdingEvidenceScreen:
    """Pin catalogue reads and the atomic service to one active bucket."""
    normalized_bucket = bucket_id.strip()
    if not normalized_bucket or filing_year < 1:
        raise ValueError("an admitted bucket and filing year are required")
    invoices = InvoiceCatalogueRepository(
        bucket_id=normalized_bucket,
        objects=secure_object_repository_for_bucket(normalized_bucket),
    )

    def lookup(invoice_id: str):
        catalogue, revision_id = invoices.load_revisioned()
        invoice = _resolve_visible_invoice(catalogue, invoice_id)
        if invoice is None:
            return None
        return invoice, revision_id

    return WithholdingEvidenceScreen(
        door=TuiWithholdingDoor(service=build_withholding_observation_service(bucket_id=normalized_bucket)),
        invoice_lookup=lookup,
        filing_year=filing_year,
    )


def _resolve_visible_invoice(catalogue: InvoiceCatalogue, supplied: str) -> Invoice | None:
    """Resolve an ID/prefix, or one exact operator-visible invoice number.

    Invoice numbers need not be globally unique.  An ambiguous number refuses
    instead of choosing a recipient or liability silently.
    """
    try:
        return resolve_catalogue_invoice(catalogue, supplied)
    except InvoiceNotFoundError:
        matches = tuple(invoice for invoice in catalogue.values() if invoice.invoice_number == supplied.strip())
        return matches[0] if len(matches) == 1 else None
    except CadrumoError:
        return None


__all__ = ["compose_installed_withholding_screen"]
