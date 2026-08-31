"""Closed axes for the facts an IVA classification is derived from.

Two enums, kept together because they answer the two halves of one question:
WHERE a classifier input came from, and WHAT the document's printed identifier
actually establishes about the counterparty.

The second one exists because the obvious answer is wrong in a way that costs
money. See :class:`CounterpartyTaxablePersonStatus`.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ClassifierInputSource",
    "CounterpartyTaxablePersonStatus",
]


class ClassifierInputSource(StrEnum):
    """Where one classifier input came from, which decides how it can be audited.

    Deliberately separate from :class:`~core.FieldOrigin`. That enum answers
    "how was this value obtained **from a source document**" and every one of
    its members names a way of reading a page. A taxpayer's own censo-registered
    regime is not read from the page at all — it is a system-authoritative fact
    about the filer that would be identical whichever document was being
    classified — so recording it under a document-reading origin would make the
    envelope claim the document said something it never said.

    Attributes:
        DOCUMENT_EVIDENCE: Established by the document, and therefore anchorable
            to a printed form an operator can be pointed at.
        PROFILE_AUTHORITY: Supplied by the taxpayer's own registered profile.
            Authoritative for the filer's own status and carries no anchor,
            because there is no printed form on the document to point at.
        OPERATOR_ASSERTION: Stated by the operator at confirm, for a fact
            neither the document nor the profile settles. Carries no anchor --
            there is no printed form, which is precisely why it had to be
            asserted -- and no profile authority either, because the vouching
            party is the operator themselves. It is a third kind of backing
            rather than a variant of the other two: an auditor asking "why does
            this record say the customer is a taxable person?" needs to be sent
            to a person, not to a page or to the censo.
    """

    DOCUMENT_EVIDENCE = "document_evidence"
    PROFILE_AUTHORITY = "profile_authority"
    OPERATOR_ASSERTION = "operator_assertion"


class CounterpartyTaxablePersonStatus(StrEnum):
    """What the document establishes about the counterparty being a taxable person.

    **Two members, and the absent third one is the point.** There is no
    ``CONSUMER`` here, because no document establishes it: a factura
    simplificada legitimately prints no recipient at all, so "no identifier
    printed" is the normal shape of a whole legitimate population rather than
    evidence about who the recipient was. A taxonomy offering ``CONSUMER``
    invites absence to be read as it, which would silently reclassify every
    simplified ticket.

    **This is deliberately not** :class:`~domain.iva.CustomerTaxStatus`, and the
    gap between them is a legal one rather than a modelling preference. That
    enum's ``B2B_IVA_REGISTERED`` is the trigger for the intra-community supply
    rule, which classifies the operation EXEMPT under LIVA art. 25 — and that
    exemption requires the customer's IVA identification number to be *verified
    as valid*, which is what a VIES consultation does. A number merely printed
    on a page has not been verified by anyone. Promoting it to
    ``B2B_IVA_REGISTERED`` would let an unverified identifier zero-rate a sale
    that may well be taxable, which is under-declaration produced by treating a
    proxy as an authority.

    So a printed identifier establishes exactly this much: someone who prints a
    IVA identifier is acting as a taxable person. Whether they are *registered*
    is a separate claim, for a separate authority, and this enum does not make
    it.

    Attributes:
        TAXABLE_PERSON: The document printed a counterparty tax identifier.
            Anchorable to that printed form.
        UNKNOWN: No counterparty identifier was established. Never an assertion
            about the counterparty — an assertion that nothing was established.
    """

    TAXABLE_PERSON = "taxable_person"
    UNKNOWN = "unknown"
