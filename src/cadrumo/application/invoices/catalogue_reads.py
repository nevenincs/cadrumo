"""Repository-backed invoice link-consistency query.

:func:`verify_invoice_repository_links` loads both the
:class:`InvoiceCatalogueRepository` and the
:class:`TransactionCatalogueRepository` for an explicit bucket, because a
one-sided link is only meaningful across the pair.
"""

from __future__ import annotations

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...domain.invoices.service import LinkInconsistency, verify_link_consistency


def verify_invoice_repository_links(*, bucket_id: str) -> tuple[LinkInconsistency, ...]:
    """Load both catalogues and return one-sided invoice/transaction links as a tuple of :class:`LinkInconsistency`."""
    return verify_link_consistency(
        InvoiceCatalogueRepository(bucket_id=bucket_id).load(),
        TransactionCatalogueRepository(bucket_id=bucket_id).load(),
    )
