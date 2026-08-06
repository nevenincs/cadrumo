"""LIVA art. 75 devengo-date resolution for one invoice record.

Art. 75.Uno binds the general regime to the operation date -- when the entrega
or prestación actually took place -- not to the bank movement or the invoice's
issue date. Art. 75.Dos moves devengo forward to the date of collection for a
pago anticipado, "por los importes efectivamente percibidos", except for the
entregas comprendidas en el artículo 25 (an entrega intracomunitaria exenta,
which always devengues under art. 75.Uno.8.º regardless of any advance
received).

:class:`~cadrumo.domain.invoices.Invoice` already carries both cases behind
one field: :attr:`~cadrumo.domain.invoices.Invoice.operation_date` records the
date, and :attr:`~cadrumo.domain.invoices.Invoice.operation_date_role` records
which of art. 75's two clauses it answers. The art. 25 exclusion and the
"money was actually received" precondition are enforced at construction time
on the invoice itself, so a record carrying an ``ADVANCE_PAYMENT_RECEIVED``
role that reaches this module is already a legally consistent one; this
module supplies nothing beyond reading the fact the invoice already declares.

Threading this date into period attribution -- so a quarter's IVA aggregation
actually selects on it rather than on the invoice's issue date -- is separate,
later work (the invoice equivalent of the ledger-transaction devengo span
:func:`~cadrumo.domain.transactions.transaction_eligible_date_span` already
resolves). This module is the fact the future wiring will read; a single,
full-amount pago anticipado already resolves correctly through it today. A
staged schedule of several partial advance payments, each devengoing
separately for its own amount, is not representable by a single date and is
not attempted here.

See Also:
    :attr:`cadrumo.domain.invoices.Invoice.operation_date`
        The recorded devengo-relevant date this module reads.
    :attr:`cadrumo.domain.invoices.Invoice.operation_date_role`
        The discriminator naming which art. 75 clause the date answers.
    :func:`cadrumo.domain.transactions.transaction_eligible_date_span`
        The equivalent ledger-transaction-side devengo span, already wired
        into IVA period attribution.
"""

from __future__ import annotations

from datetime import date

from ...domain.invoices import Invoice

__all__ = ["invoice_devengo_date"]


def invoice_devengo_date(invoice: Invoice) -> date:
    """Return the LIVA art. 75 devengo date for one invoice.

    Args:
        invoice: The invoice whose devengo date is being resolved.

    Returns:
        :attr:`~cadrumo.domain.invoices.Invoice.operation_date` when the
        invoice records one (either art. 75.Uno's operation date or
        art. 75.Dos's collection date -- both are read identically here,
        the role exists to say WHICH clause supplied the date, not to change
        how it is used), otherwise :attr:`~cadrumo.domain.invoices.Invoice.issued_at`
        -- the issue-date proxy this record exists to move away from.
    """
    return invoice.operation_date or invoice.issued_at
