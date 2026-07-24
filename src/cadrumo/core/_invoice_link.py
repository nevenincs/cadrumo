"""Closed direction axis for a one-sided invoice/transaction link.

An invoice and a ledger transaction cite each other: the invoice carries the
transaction in ``linked_transaction_ids`` and the transaction carries the
invoice in ``invoice_id``. A link is *one-sided* when only one of those
citations exists, which is what
:func:`cadrumo.domain.invoices.verify_link_consistency` reports as a
:class:`~cadrumo.domain.invoices.LinkInconsistency`.

The axis is declared here in ``core/`` -- the innermost hexagonal ring -- so
the domain record, the operator-facing CLI payload, and tests all name the
same two members rather than re-declaring the token pair at each boundary.

This module deliberately declares tokens only. Detecting a one-sided link
stays in the invoice domain service, and the write that makes such a link
unreachable stays in the application linking service.
"""

from __future__ import annotations

from enum import StrEnum


class LinkInconsistencyDirection(StrEnum):
    """Which catalogue cites the other without being cited back.

    Attributes:
        INVOICE_ONLY: The invoice lists the transaction, but the transaction's
            ``invoice_id`` does not point back at that invoice (or the
            transaction is absent entirely).
        TRANSACTION_ONLY: The transaction names the invoice, but the invoice's
            ``linked_transaction_ids`` does not contain that transaction (or
            the invoice is absent entirely).
    """

    INVOICE_ONLY = "invoice-only"
    TRANSACTION_ONLY = "transaction-only"


__all__ = ["LinkInconsistencyDirection"]
