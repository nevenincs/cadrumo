"""Repository-backed invoice link-consistency query.

:func:`verify_invoice_repository_links` loads both catalogue projections from
the required application read ports, because a one-sided link is only
meaningful across the pair. A caller that already holds the whole transaction
catalogue passes it instead of having it read again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domain.invoices.service import LinkInconsistency, verify_link_consistency
from .catalogue_reads_ports import InvoiceCatalogueReadPorts

if TYPE_CHECKING:
    from ...domain.transactions.models import TransactionCatalogue


def verify_invoice_repository_links(
    *,
    ports: InvoiceCatalogueReadPorts,
    transactions: TransactionCatalogue | None = None,
) -> tuple[LinkInconsistency, ...]:
    """Load both catalogues and return one-sided invoice/transaction links.

    ``transactions`` must be the whole :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`,
    never a period's
    rows: a row outside the caller's period can still hold a one-sided link.
    """
    return verify_link_consistency(
        ports.invoice_reader.load(),
        transactions if transactions is not None else ports.transaction_reader.load(),
    )
