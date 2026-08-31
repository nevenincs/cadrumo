"""Direction-resolved projections over a read invoice draft.

A draft is pre-direction by construction: the readers record what each party's
block said without deciding which of them the filer is. Everything here answers
a question that only becomes answerable once the operator states the direction,
or once a record has been minted -- so these are projections of a draft rather
than part of reading one.

Two projections live here, and both exist because a caller recomputing them
would be a second authority on one answer:

- :func:`counterparty_draft_side` selects which side of the document is the
  COUNTERPARTY, totally and with no fall-back to the other side. Every consumer
  reads the same selection, so a document cannot resolve to the customer for one
  caller and the supplier for another.
- :func:`printed_total_discrepancy` reports the document's own printed total
  disagreeing with the total actually recorded. The printed figure never
  overwrites the derived one; it is the free cross-check that catches a recargo
  with nowhere to go, an unread rate resolving to the exempt slot, and a misread
  base.

Reading a document into a draft lives in
:mod:`~application.ledger.invoice_draft_extraction`; confirming a reviewed draft
into a catalogue record lives in
:mod:`~application.ledger.invoice_confirmation`.

See Also:
    :class:`~application.ledger.invoice_draft_records.InvoiceDraft`
        The pre-direction draft these projections read.
    :func:`~application.ledger.closure_findings.closure_findings`
        The document-internal arithmetic check, distinct from the
        printed-versus-recorded comparison here.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.invoices.models import Invoice
from ...domain.iva.classification import InvoiceKind
from .invoice_draft_records import InvoiceDraft

__all__ = [
    "CounterpartyDraftSide",
    "PrintedTotalDiscrepancy",
    "counterparty_draft_side",
    "printed_total_discrepancy",
]


class CounterpartyDraftSide(BaseModel):
    """The side of a read document that is the COUNTERPARTY, once direction is known.

    A draft is pre-direction by construction: it records what each party's block
    said without deciding which of them the filer is. Direction settles that, and
    settles it the same way for every consumer -- which is why this is a record
    produced once rather than a pair of field lookups each caller repeats.

    Attributes:
        tax_id: The counterparty's identifier as the document printed it, or
            ``None`` when the reader recovered none.
        name: The counterparty's stated name, or ``None``.
        postal_code: The postal code printed in the counterparty's address, or
            ``None``.
        country: The country NAME printed in the counterparty's address, or
            ``None``. A name rather than a code, because that is what an address
            block prints; the match against the bounded vocabulary is the
            establishment ladder's own second rung.
        country_code: The ISO 3166-1 alpha-2 country code a structured record
            stated for the counterparty, or ``None``. Carried beside the printed
            NAME rather than instead of it: the two are the same ladder rung
            reached from different readers, and a document states one or the
            other, never both.
        stated_country_token: The token the record's country element carries,
            verbatim, or ``None`` where it stated none. Carried beside the
            resolved code rather than folded into it, because the two answer
            different questions and only this one can answer the second: the
            resolved field is empty both for a document that stated no country
            AND for one stating a token the bundled vocabulary does not carry,
            so a consumer asking "did the document state a country" off that
            field gets the same answer for an unplaceable export and for an
            invoice with no address block. A consumer deciding whether an
            unestablished counterparty is the DOCUMENT's gap or OURS depends on
            telling those apart.

            **Named a TOKEN, and not a country CODE, deliberately.**
            The establishment ladder's ``resolved_country_code`` parameter wants
            the RESOLVED alpha-2 -- which is ``country_code`` above, and
            which is what this object's one ladder call site correctly passes.
            Two same-shaped attributes on one object, one safe in that slot and
            one not, is a swap that type-checks: both are ``str | None``, and
            feeding an alpha-3 into an alpha-2 parameter on a tax-territory path
            fails to place the country and reintroduces exactly the silence this
            field exists to remove. The name is the guard, because nothing else
            here is.
        tax_id_field: Which draft field ``tax_id`` was taken from. Carried so an
            operator override is recorded against the reading it displaced
            rather than against whichever field shares the option's name.
        name_field: The same for ``name``.
    """

    model_config = STRICT_FROZEN_CONFIG

    tax_id: str | None = None
    name: str | None = None
    postal_code: str | None = None
    country: str | None = None
    country_code: str | None = None
    stated_country_token: str | None = None
    tax_id_field: str = Field(min_length=1)
    name_field: str = Field(min_length=1)


def counterparty_draft_side(draft: InvoiceDraft, *, kind: InvoiceKind) -> CounterpartyDraftSide:
    """Select the counterparty's side of a draft from the document's direction.

    On an invoice the filer ISSUED, the counterparty is the customer; on one
    they RECEIVED, it is the supplier.

    **The selection is total, with no fall-back to the other side, and that is
    the load-bearing part.** This once read the customer side "if it is set,
    otherwise the supplier", and because the text and vision readers cannot
    populate a customer at all, every issued document silently resolved to the
    supplier -- who, on a document the filer issued, IS the filer. The value is
    checksum-valid, so every identity check downstream passes it, and it is
    bound for the Modelo 347 / 349 totals AEAT reconciles against the other
    party's own declaration.

    Two guards elsewhere do catch that today, but both load the taxpayer profile
    and both return without refusing when it carries no tax id, so the
    protection was only ever as present as the profile. Selecting one side and
    stopping makes the property structural instead: an unread counterparty stays
    ``None`` and is refused as a missing field, naming the override that supplies
    it, which is the same outcome an operator already gets for any other field
    the reader could not recover.

    Args:
        draft: The pre-direction reading of the document.
        kind: Which side of the invoice the filer is on, as the operator settled
            it at confirm. Never the reader's suggestion.

    Returns:
        :class:`CounterpartyDraftSide`: the selected side, and which draft
        fields it came from.
    """
    if kind is InvoiceKind.ISSUED:
        return CounterpartyDraftSide(
            tax_id=draft.customer_tax_id,
            name=draft.customer_name,
            country_code=draft.customer_country_code,
            stated_country_token=draft.customer_stated_country_code,
            postal_code=draft.customer_postal_code,
            country=draft.customer_country,
            tax_id_field="customer_tax_id",
            name_field="customer_name",
        )
    return CounterpartyDraftSide(
        tax_id=draft.supplier_tax_id,
        name=draft.supplier_name,
        country_code=draft.supplier_country_code,
        stated_country_token=draft.supplier_stated_country_code,
        postal_code=draft.supplier_postal_code,
        country=draft.supplier_country,
        tax_id_field="supplier_tax_id",
        name_field="supplier_name",
    )


class PrintedTotalDiscrepancy(BaseModel):
    """The document's printed total disagreeing with the total actually recorded.

    The confirm path never persists a model-read or text-read figure as the
    invoice total: ``grand_total`` is DERIVED from the taxable base and the
    registry-resolved rate slot
    (:func:`~application.invoices.build_catalogue_invoice`). That derivation is
    the correct behaviour and this record does not change it -- the printed
    figure stays an advisory cross-check and never overwrites the derived value,
    exactly as the evidence-reading discipline requires.

    What this record adds is the other half of that same discipline: when the
    two disagree, say so. A disagreement is never noise, because the derived
    total is arithmetically fixed at ``base + cuota``; anything the document
    prints beyond that is a component the record could not represent, or a
    misread of one it could:

    - A **recargo de equivalencia** invoice (LIVA art. 161) prints
      ``base + cuota + recargo``. The recargo has nowhere to go on this path,
      so the record silently understates the document by exactly that surcharge.
    - An **unread rate** resolves to :attr:`~domain.invoices.IvaRate.EXEMPT`
      (``iva_rate=None`` is the base-only slot), minting a zero-cuota invoice
      whose printed total still shows the cuota that was charged.
    - A **misread base** propagates into the derived total and diverges from the
      printed one.

    All three are silent under-declarations that the printed total detects for
    free, having already been read. Discarding it unexamined is what let them
    through.

    Attributes:
        printed_total: The total actually printed on the document, as recovered
            by the on-host reader.
        recorded_total: The total derived from the confirmed base and rate slot,
            i.e. what the persisted invoice carries.
        difference: ``printed_total - recorded_total``. Positive means the
            document totals MORE than the record -- the under-declaration
            direction, and the one a recargo produces.
    """

    model_config = STRICT_FROZEN_CONFIG

    printed_total: Decimal
    recorded_total: Decimal
    difference: Decimal


def printed_total_discrepancy(*, draft: InvoiceDraft, invoice: Invoice) -> PrintedTotalDiscrepancy | None:
    """Return the printed-vs-recorded total disagreement, or ``None`` when they agree.

    Compares only when the reader actually recovered a total: a document whose
    total could not be read grounds no cross-check, and reporting a discrepancy
    against an absent figure would manufacture an alert out of missing data
    rather than out of conflicting data.

    Args:
        draft: The extraction the confirmation was based on.
        invoice: The invoice that was persisted (or matched on a guarded no-op).

    Returns:
        :class:`PrintedTotalDiscrepancy` when the document printed a total that
        differs from the recorded one, else ``None``.
    """
    printed = draft.grand_total
    if printed is None:
        return None
    if printed == invoice.grand_total:
        return None
    return PrintedTotalDiscrepancy(
        printed_total=printed,
        recorded_total=invoice.grand_total,
        difference=printed - invoice.grand_total,
    )
