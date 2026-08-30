"""One authority for the bank-direction to invoice-issuance mapping.

Every ledger surface that needs to know whether a bank movement represents an
invoice the taxpayer *issued* or one they *received* asks this module, so the
answer is decided once. Three private copies of the mapping previously lived in
:mod:`~application.aggregation._iva_ledger`,
:mod:`~application.aggregation._evidence_advisory` and
:mod:`~application.modelo._ledger_evidence_gate`, byte-identical and
independently maintained.

Home
----
This lives in the application layer rather than beside
:class:`~cadrumo.domain.iva.InvoiceKind`, deliberately. The mapping joins a
:class:`~cadrumo.domain.transactions.TransactionDirection` to an
``InvoiceKind``, and ``domain.iva`` imports nothing from ``domain.transactions``
today. Placing it there would mint a new cross-domain edge to host a function
whose only callers are in ``application`` — the same reasoning that keeps
``InvoiceKind`` itself in ``domain.iva``. ``_business_proportion`` is the
established precedent for a one-decision application module shared across the
aggregation surfaces.

A known limit, stated rather than hidden
----------------------------------------
The mapping is a function of direction ALONE, and that is not sufficient for
every real row. A supplier refund or credit note on a returned purchase is an
``INCOMING`` movement, so it resolves here to ``ISSUED`` and is settled as
output IVA, where the correct treatment corrects input IVA. Consolidating the
three copies does NOT fix that; it makes the fix land in one place instead of
three.

The reason the fix is not simply "consult the purchase-evidence id here" is that
``InvoiceKind`` cannot express the answer. It is a two-member unsigned axis, and
ledger amounts are absolute magnitudes by standing convention, so returning
``RECEIVED`` for a refund would add to deducible input IVA rather than reduce
it — trading one wrong figure for another. The renta side models the same event
as a third, signed disposition. Which representation the IVA side adopts is not
yet settled; when it is, it changes this function and nothing else.
"""

from __future__ import annotations

from ...domain.iva.classification import InvoiceKind
from ...domain.transactions.enums import TransactionDirection

__all__ = ["invoice_kind_for_direction"]


def invoice_kind_for_direction(direction: TransactionDirection | None) -> InvoiceKind | None:
    """Map a bank movement's direction onto the invoice-issuance axis.

    ``INCOMING`` money is treated as a sale the taxpayer issued (output IVA);
    ``OUTGOING`` money as a purchase they received (input IVA).

    Args:
        direction: The bank movement's direction, or ``None`` when the caller
            could not resolve one from a persisted evidence row.

    Returns:
        The corresponding :class:`~cadrumo.domain.iva.InvoiceKind`, or ``None``
        for any direction that is not an IVA settlement flow —
        ``INTERNAL_TRANSFER`` and the unresolved case — so the caller can reject
        the row rather than guess at a treatment for it.

        Note the deliberate limit in the module docstring: the refund of a
        purchase is an ``INCOMING`` movement and resolves to ``ISSUED`` here.
    """
    if direction is TransactionDirection.INCOMING:
        return InvoiceKind.ISSUED
    if direction is TransactionDirection.OUTGOING:
        return InvoiceKind.RECEIVED
    return None
