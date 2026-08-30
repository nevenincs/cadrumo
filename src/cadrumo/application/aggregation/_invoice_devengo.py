"""LIVA art. 75 devengo resolution and period attribution for one invoice record.

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
module supplies nothing beyond reading the fact the invoice already declares
and, where the invoice declares nothing, saying so out loud.

That last part is why the resolution is a record and not a date. Not every
invoice carries a recorded operation date, so a fallback exists, and a
fallback that returns a bare date collapses two structurally different answers
-- a declared legal fact and a substitute for one -- into one indistinguishable
return. The issue date is a substitute that agrees with the fact for every
operation invoiced inside its own period and diverges exactly at the month and
quarter boundaries where attribution changes, so the difference is the whole
point.
:class:`~cadrumo.core.aggregation.InvoiceDevengoRank` carries it.

:func:`invoice_devengo_in_period` is the single period-attribution predicate
for the invoice catalogue. Every aggregation path that asks "does this invoice
belong to this filing period" calls it rather than comparing a date of its own
choosing, so the calculate path and the Sheets pull path cannot answer the
question differently: there is one implementation and both consume it.

A staged schedule of several partial advance payments, each devengoing
separately for its own amount, is not representable by a single date and is
not attempted here.

See Also:
    :attr:`cadrumo.domain.invoices.Invoice.operation_date`
        The recorded devengo-relevant date this module reads.
    :attr:`cadrumo.domain.invoices.Invoice.operation_date_role`
        The discriminator naming which art. 75 clause the date answers.
    :class:`cadrumo.core.aggregation.InvoiceDevengoRank`
        The marker naming which source produced the resolved date.
    :func:`cadrumo.domain.transactions.transaction_eligible_date_span`
        The equivalent ledger-transaction-side devengo span, already wired
        into IVA period attribution.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel

from ...core.aggregation import InvoiceDevengoRank
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ._source_mesh import CalculationSourceDiagnostic

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ...core.period import Period
    from ...domain.invoices.models import Invoice

__all__ = [
    "InvoiceDevengo",
    "devengo_proxy_attribution_diagnostics",
    "invoice_devengo_in_period",
    "proxy_attributed_invoice_ids",
    "resolve_invoice_devengo",
]

_PROXY_SAMPLE_LIMIT: Final = 5
"""How many invoice numbers the advisory names before eliding the rest.

Chosen so the rendered message stays inside
:data:`~application.aggregation.DIAGNOSTIC_MESSAGE_MAX_LENGTH` for realistic
invoice numbering. The bound truncates rather than raises, so overflowing it
would silently swallow the elision notice and leave the operator reading a
sample they could not tell was incomplete.
"""


class InvoiceDevengo(BaseModel):
    """The date one invoice files under, and where that date came from.

    The two fields are read together or not at all. A consumer that takes
    :attr:`devengo_date` while ignoring :attr:`rank` has re-created the bare
    return this record exists to replace, and will treat a proxy as a declared
    fact at exactly the boundary where the two disagree.

    Attributes:
        devengo_date: The resolved LIVA art. 75 devengo date.
        rank: Which source produced it.
    """

    model_config = _STRICT_FROZEN

    devengo_date: date
    rank: InvoiceDevengoRank


def resolve_invoice_devengo(invoice: Invoice) -> InvoiceDevengo:
    """Return the LIVA art. 75 devengo date for one invoice, with its rank.

    Args:
        invoice: The invoice whose devengo date is being resolved.

    Returns:
        The recorded :attr:`~cadrumo.domain.invoices.Invoice.operation_date`
        ranked :attr:`~cadrumo.core.aggregation.InvoiceDevengoRank.OPERATION_DATE_DECLARED`
        when the invoice carries one -- either art. 75.Uno's operation date or
        art. 75.Dos's collection date, both read identically here because the
        role says WHICH clause supplied the date, not how it is used --
        otherwise :attr:`~cadrumo.domain.invoices.Invoice.issued_at` ranked
        :attr:`~cadrumo.core.aggregation.InvoiceDevengoRank.ISSUE_DATE_PROXY`.
    """
    operation_date = invoice.operation_date
    if operation_date is not None:
        return InvoiceDevengo(
            devengo_date=operation_date,
            rank=InvoiceDevengoRank.OPERATION_DATE_DECLARED,
        )
    return InvoiceDevengo(devengo_date=invoice.issued_at, rank=InvoiceDevengoRank.ISSUE_DATE_PROXY)


def invoice_devengo_in_period(invoice: Invoice, *, period: Period) -> bool:
    """Return whether *invoice* devengues inside *period*.

    The single period-attribution predicate for the invoice catalogue. It
    selects on the art. 75 devengo date rather than on the issue date, so an
    operation performed in one quarter and invoiced in the next is declared in
    the quarter it was performed.

    Args:
        invoice: The invoice being attributed.
        period: The filing period, which must carry a calendar span.

    Returns:
        Whether the resolved devengo date falls inside the period's inclusive
        span.
    """
    return period.contains(resolve_invoice_devengo(invoice).devengo_date)


def proxy_attributed_invoice_ids(invoices: Iterable[Invoice]) -> tuple[str, ...]:
    """Return the sorted ids of *invoices* attributed on the issue-date proxy.

    The reporting half of the rank. An aggregation path hands it the invoices
    it actually folded in, and a non-empty result names the records whose
    period placement rests on a substitute rather than on a recorded devengo
    date -- the set an operator has to see before filing, because those are the
    records that would move quarter if the real date were recorded.

    Args:
        invoices: The invoices a period's figures were built from.

    Returns:
        The sorted invoice ids ranked
        :attr:`~cadrumo.core.aggregation.InvoiceDevengoRank.ISSUE_DATE_PROXY`,
        empty when every contributing invoice declared its own devengo date.
    """
    return tuple(
        sorted(
            invoice.invoice_id
            for invoice in invoices
            if resolve_invoice_devengo(invoice).rank is InvoiceDevengoRank.ISSUE_DATE_PROXY
        ),
    )


def devengo_proxy_attribution_diagnostics(
    invoices: Iterable[Invoice],
    *,
    source_kind: str,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return the non-blocking advisory for a period built on proxy-ranked invoices.

    One shared builder rather than a per-resolver message, so every aggregation
    path that folds in invoices discloses the substitution in the same words.
    A path that phrased it for itself would let the same taxpayer see the same
    condition described two ways depending on which modelo they were filing.

    Non-blocking by design. The issue date is the best available attribution
    and refusing on it would make an ordinary catalogue unfileable; what the
    operator needs is to know the period placement is a substitution before
    they file, which is what the advisory says.

    Args:
        invoices: The invoices this period's figures were built from.
        source_kind: The binding source kind the calling resolver owns.
        resolver_id: The calling resolver's id.

    Returns:
        One advisory naming the proxy-attributed records, or an empty tuple
        when every contributing invoice declared its own devengo date.
    """
    proxied = tuple(
        invoice for invoice in invoices if resolve_invoice_devengo(invoice).rank is InvoiceDevengoRank.ISSUE_DATE_PROXY
    )
    if not proxied:
        return ()
    # Named by invoice NUMBER, not by the content-addressed id every other
    # diagnostic on this surface carries. The remedy asks the operator to open
    # each record and record a date, and the number is what they see in the
    # catalogue listing; a 64-hex digest would also exhaust the message bound
    # after two entries and elide the rest of the sample.
    numbers = sorted(invoice.invoice_number for invoice in proxied)
    sample = ", ".join(numbers[:_PROXY_SAMPLE_LIMIT])
    elided = len(numbers) - len(numbers[:_PROXY_SAMPLE_LIMIT])
    suffix = f" and {elided} more" if elided else ""
    return (
        CalculationSourceDiagnostic(
            reason="devengo_date_proxy_attribution",
            source_kind=source_kind,
            resolver_id=resolver_id,
            message=(
                f"{len(numbers)} invoice(s) were placed in this filing period on their issue "
                f"date because no operation date is recorded on them: {sample}{suffix}. "
                "LIVA art. 75.Uno binds the devengo to the date the entrega or prestacion took "
                "place, and an invoice may lawfully be issued in a later period than the one "
                "its operation belongs to, so this placement is a substitution, not a legal "
                "determination"
            ),
            remedy=(
                "Record the fecha de operacion on each invoice named so its period is "
                "determined by the art. 75 devengo date rather than inferred from the issue date"
            ),
            # Advisory-asserted: this module holds no revision, snapshot or
            # casilla definition anywhere -- devengo attribution applies
            # uniformly across every IVA-relevant modelo, so there is no
            # single casilla whose own ref this could read instead.
            asserted_legal_refs=("ley-37-1992:art-75",),
        ),
    )
