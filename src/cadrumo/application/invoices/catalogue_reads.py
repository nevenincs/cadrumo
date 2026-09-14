"""Repository-backed invoice link-consistency query.

:func:`verify_invoice_repository_links` loads both catalogue projections from
the required application read ports, because a one-sided link is only
meaningful across the pair.
"""

from __future__ import annotations

from ...domain.invoices.service import LinkInconsistency, verify_link_consistency
from .catalogue_reads_ports import InvoiceCatalogueReadPorts


def verify_invoice_repository_links(*, ports: InvoiceCatalogueReadPorts) -> tuple[LinkInconsistency, ...]:
    """Load both catalogues and return one-sided invoice/transaction links."""
    return verify_link_consistency(
        ports.invoice_reader.load(),
        ports.transaction_reader.load(),
    )
