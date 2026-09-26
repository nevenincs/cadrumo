"""Compose the existing withholding screen for an admitted installed bucket.

The launcher supplies the active bucket and filing year.  Invoice and ledger
payment lookups are reads of that bucket's encrypted catalogues; all mutations
remain in the shared withholding observation service used by the CLI.  The
filer's schedule is read from the bucket's profile at each capture, so a
profile change while the screen is open is honoured.

Core types:
:class:`~cadrumo.domain.invoices.models.InvoiceCatalogue`,
:class:`~cadrumo.domain.transactions.models.TransactionCatalogue`,
:class:`~cadrumo.adapters.persistence.profile.transactions.TransactionCatalogueRepository`.
"""

from __future__ import annotations

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ....application.aggregation.withholding_filing_cadence import (
    WithholdingFilerCadence,
    load_bucket_withholding_filer_cadence,
)
from ....application.invoices.catalogue_lifecycle import resolve_catalogue_invoice
from ....core.errors.hierarchy import CadrumoError
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.invoices.errors import InvoiceNotFoundError
from ....domain.invoices.models import Invoice, InvoiceCatalogue
from ....domain.transactions.models import TransactionCatalogue
from ...adapter_composition import build_withholding_observation_service
from .door import TuiWithholdingDoor
from .screen import WithholdingEvidenceScreen


def compose_installed_withholding_screen(*, bucket_id: str, filing_year: int) -> WithholdingEvidenceScreen:
    """Pin catalogue reads and the atomic service to one active bucket."""
    normalized_bucket = bucket_id.strip()
    if not normalized_bucket or filing_year < 1:
        raise ValueError("an admitted bucket and filing year are required")
    objects = secure_object_repository_for_bucket(normalized_bucket)
    invoices = InvoiceCatalogueRepository(bucket_id=normalized_bucket, objects=objects)
    transactions = TransactionCatalogueRepository(bucket_id=normalized_bucket, objects=objects)

    def lookup(invoice_id: str):
        catalogue, revision_id = invoices.load_revisioned()
        invoice = _resolve_visible_invoice(catalogue, invoice_id)
        if invoice is None:
            return None
        return invoice, revision_id

    def ledger_payment_lookup(transaction_id: str) -> tuple[TransactionCatalogue, str | None]:
        return _read_ledger_payment(transactions, transaction_id)

    def filer_cadence(year: int) -> WithholdingFilerCadence:
        with bundled_indexed_authority().operation() as operation:
            return load_bucket_withholding_filer_cadence(
                bucket_id=normalized_bucket,
                filing_year=year,
                operation=operation,
            )

    return WithholdingEvidenceScreen(
        door=TuiWithholdingDoor(
            service=build_withholding_observation_service(bucket_id=normalized_bucket),
            filer_cadence=filer_cadence,
        ),
        invoice_lookup=lookup,
        ledger_payment_lookup=ledger_payment_lookup,
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


def _read_ledger_payment(
    transactions: TransactionCatalogueRepository,
    transaction_id: str,
) -> tuple[TransactionCatalogue, str | None]:
    """Read one addressed transaction between two catalogue revision reads.

    The revision is withheld (``None``) when it cannot be stated or moved
    during the read, so a capture never rests on a row that changed under it.
    Only the exact id is read: a payroll payment is addressed, never guessed
    from a prefix or a visible description.
    """
    revision_id = transactions.load_revision()
    catalogue = transactions.load_by_ids((transaction_id,))
    if revision_id is None or transactions.load_revision() != revision_id:
        return catalogue, None
    return catalogue, revision_id


__all__ = ["compose_installed_withholding_screen"]
