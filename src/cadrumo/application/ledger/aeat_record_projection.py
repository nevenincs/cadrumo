"""Project one AEAT-declared record onto the single-counterparty ledger shape.

The consumer the batch reader
(:func:`~adapters.inbound.einvoice.parse_aeat_record_batch`) named and did not
have. That reader carries every recipient a SII or VERI*FACTU record states,
because ``IDDestinatario`` is ``[0..1000]`` in the schema and a party set cannot
be split back apart once discarded. The constraint that only ONE counterparty
fits belongs here, at the projection, and this module is where it is enforced.

Two cases are legitimate and one is not:

**Zero recipients is valid and meaningful.** ``Destinatarios`` is ``[0..1]``, so
a factura simplificada legitimately names nobody. This projection returns
``None`` for that case rather than refusing -- guarding ``!= 1`` instead of
``> 1`` would reject a whole legitimate document class.

**Exactly one recipient projects.** The ordinary case.

**More than one recipient REFUSES, by name.** A record naming several recipients
cannot become a single-counterparty ledger record without discarding parties,
and the discard is what makes the failure quiet: the resulting record is
well-formed, reconciles arithmetically, and names a real counterparty -- just
not all of them. The refusal therefore enumerates every recipient WITH the
identifier scheme each was stated under, because a party given through
``IDOtro`` carries a country and an AEAT id-type code rather than a NIF, and an
operator resolving the split needs to know which identifier they are looking at.

This module makes no decision about what to DO with a projected counterparty.
The batch reader's own docstring is explicit that these records are the
taxpayer's own declarations and must never stand in for the evidence a
counterparty issued; the projection here is for declared-versus-recorded
reconciliation only.

See Also:
    :func:`~adapters.inbound.einvoice.parse_aeat_record_batch`
        The batch reader whose inherited multi-recipient requirement this
        module discharges.
    :class:`~application.ledger.invoice_draft_records.InvoiceDraft`
        The single-counterparty draft shape a projected record targets.
"""

from __future__ import annotations

from ...adapters.inbound.einvoice.record_batch import AeatParty, ParsedAeatRecord
from ...core.errors.hierarchy import CadrumoError

__all__ = [
    "AeatRecordProjectionError",
    "describe_aeat_party_identifier",
    "project_aeat_record_counterparty",
]


class AeatRecordProjectionError(CadrumoError):
    """Raised when a declared record cannot project onto one counterparty."""


def describe_aeat_party_identifier(party: AeatParty) -> str:
    """Return a party rendered with the identifier SCHEME it was stated under.

    The scheme is the load-bearing half. A Spanish party states a ``NIF``; a
    foreign one is stated through ``IDOtro``, which carries a country code and
    an AEAT id-type code, and the same digits under two schemes are two
    different parties. Rendering only the digits would produce a refusal that
    names parties an operator cannot tell apart.

    Args:
        party: The party to describe.

    Returns:
        A single-line description naming whatever the record actually stated,
        never inventing a scheme for an identifier the record left bare.
    """
    name = party.name or "(unnamed)"
    if party.tax_id is None:
        return f"{name} [no identifier stated]"
    if party.country_code is not None or party.id_type is not None:
        country = party.country_code or "?"
        id_type = party.id_type or "?"
        return f"{name} [IDOtro country={country} id_type={id_type} id={party.tax_id}]"
    return f"{name} [NIF {party.tax_id}]"


def project_aeat_record_counterparty(record: ParsedAeatRecord) -> AeatParty | None:
    """Return the record's single recipient, or refuse a multi-recipient record.

    Args:
        record: One record read from a submission batch.

    Returns:
        The sole recipient, or ``None`` when the record names none -- which a
        factura simplificada legitimately does.

    Raises:
        AeatRecordProjectionError: When the record names more than one
            recipient. The message enumerates every recipient with its
            identifier scheme so the operator can see exactly which parties the
            single-counterparty shape cannot hold, rather than being told a
            count.
    """
    if not record.recipients:
        return None
    if len(record.recipients) == 1:
        return record.recipients[0]

    described = "; ".join(describe_aeat_party_identifier(party) for party in record.recipients)
    invoice = record.invoice_number or "(no invoice number stated)"
    raise AeatRecordProjectionError(
        f"Declared record {invoice} names {len(record.recipients)} recipients and cannot project onto a "
        f"single-counterparty ledger record: {described}. Reconcile this record per recipient rather than "
        f"as one row; taking the first would discard the rest silently.",
    )
