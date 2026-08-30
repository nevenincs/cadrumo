"""Whether the taxpayer issuing an ISSUED invoice is established in the TAI.

RD 1619/2012 art. 6.1.d makes a factura simplificada's counterparty tax id
mandatory in three cases. Case 3.º governs the DESTINATARIO's NIF for an
operation realised in the territorio de aplicación del impuesto [TAI] whose
issuer is established there: "operaciones que se entiendan realizadas en el
[TAI] y el empresario o profesional obligado a la expedición de la factura
haya de considerarse establecido en dicho territorio."

Scoped to ISSUED invoices only. The party the case asks about is whoever is
"obligado a la expedición de la factura" -- the issuer -- and that party
differs by direction: on an ISSUED invoice it is this app's own taxpayer, so
the case reduces to "does the destinatario's (the counterparty's) NIF need to
be on the document", a question this predicate can answer. On a RECEIVED
invoice the issuer is the counterparty (the supplier), and the destinatario
whose NIF case 3.º would require is the PROFILE HOLDER -- this app's own
taxpayer, whose own NIF is not a fact this record needs to track (it is
already known) and not a field :class:`~cadrumo.domain.invoices.Invoice`
carries. There is no second, RECEIVED-side version of this predicate to
build; the question case 3.º asks has no unknown left to answer there.

**This is not the same as "a received invoice's completeness is not our
concern".** RD 1619/2012 art. 6.4, read together with LIVA art. 97.Uno,
conditions the RIGHT TO DEDUCT the IVA soportado on holding a factura that
meets art. 6's content requirements: "tendrá la consideración de factura
aquella que contenga todos los datos y reúna los requisitos a que se refiere
este artículo." A supplier's non-compliant invoice is very much this
taxpayer's problem -- it is the document the deduction rests on. Nothing in
this codebase currently checks whether a RECEIVED invoice is complete enough
to support the deduction it feeds; that is a real, adjacent, UNADDRESSED gap
this module does not attempt to close (it is a different question -- factura
completeness for deduction purposes generally, not the narrow destinatario-
NIF case 3.º asks about on the ISSUED side).

:class:`~cadrumo.domain.invoices.Invoice` has nowhere to carry establishment
even for the ISSUED side -- it is a pure domain record with no profile
dependency, by design (a domain model does not reach into repository/profile
state) -- and it is not a NEW fact this app needs to learn:
:class:`~cadrumo.domain.deadlines.TaxpayerProfile` already carries
:attr:`~cadrumo.domain.deadlines.TaxpayerProfile.fiscal_residency` (TRLIRNR
RDLeg 5/2004 art. 2), which this module reads rather than duplicating.

**The approximation, stated rather than hidden, with its error direction
named.** ``fiscal_residency`` is an IRPF-RESIDENCE axis (national-level:
resident in Spain vs not); TAI establishment is an IVA-TERRITORIAL axis that
excludes Canarias (IGIC territory) and Ceuta/Melilla (IPSI territory) even
though both are part of Spain. These are two different axes that happen to
look like one word. :class:`~cadrumo.domain.deadlines.TaxpayerProfile`
carries no field distinguishing a Canarias- or Ceuta/Melilla-resident
taxpayer from a mainland one, so this predicate CANNOT currently tell them
apart: a Canarias-resident autónomo reads ``fiscal_residency ==
RESIDENT_IRPF`` (true) and is NOT established in the TAI (also true), and
this predicate returns ``True`` for both.

The error direction is OVER-STRICT, which is the safer of the two possible
mistakes: for a Canarias/Ceuta/Melilla-resident issuer, this predicate wrongly
reports "established" and so wrongly demands a counterparty NIF the law does
not actually require there. It never does the reverse (it never reports
"established" as ``False`` for someone who genuinely is). No
``EstablecimientoPermanente``-style territorial axis exists on
:class:`~cadrumo.domain.deadlines.TaxpayerProfile` today to close this;
designing one is a real schema decision with its own blast radius and is
explicitly NOT this module's job.
``test_a_canarias_or_ceuta_melilla_resident_is_a_pinned_known_limitation`` in
the test suite pins the current (wrong-but-safe) behaviour so the day that
axis is added, the test fails and points at exactly what to fix.

See Also:
    :class:`cadrumo.domain.deadlines.FiscalResidency`
        The two-member closed enum this predicate reads.
    :class:`cadrumo.domain.deadlines.TaxpayerProfile`
        Owns the per-taxpayer residency fact; one profile per bucket.
"""

from __future__ import annotations

from ...domain.deadlines import FiscalResidency, TaxpayerProfile
from ...domain.invoices.enums import InvoiceClass
from ...domain.invoices.models import Invoice
from ...domain.iva import InvoiceKind

_DOMESTIC_COUNTRY_CODE = "ES"

__all__ = ["issuer_established_in_tai", "simplificada_requires_tax_id_for_domestic_issuer"]


def issuer_established_in_tai(profile: TaxpayerProfile) -> bool:
    """Return whether the taxpayer issuing invoices under ``profile`` is established in the TAI.

    ``fiscal_residency is None`` is treated as ``RESIDENT_IRPF``, matching
    the field's own documented default for engine consumers
    (:attr:`~cadrumo.domain.deadlines.TaxpayerProfile.fiscal_residency`).

    Args:
        profile: The bucket's :class:`TaxpayerProfile`.

    Returns:
        ``True`` unless the profile declares ``NON_RESIDENT_IRNR``. See the
        module docstring for the Canarias/Ceuta/Melilla over-strict
        approximation (a known, pinned limitation) and the non-resident-
        with-permanent-establishment carve-out this predicate does not yet
        model.
    """
    return profile.fiscal_residency is not FiscalResidency.NON_RESIDENT_IRNR


def simplificada_requires_tax_id_for_domestic_issuer(invoice: Invoice, profile: TaxpayerProfile) -> bool:
    """Return whether RD 1619/2012 art. 6.1.d case 3.º makes ``invoice`` need a tax id.

    Case 3.º applies to a domestic operation (``counterparty_country ==
    "ES"``) whose issuer -- the :class:`TaxpayerProfile` holder passed as
    ``profile`` -- is established in the TAI. Scoped to
    :attr:`~cadrumo.domain.invoices.Invoice.kind` ``ISSUED`` only: case 3.º
    asks about the DESTINATARIO's NIF, which on an ISSUED invoice is the
    counterparty this predicate can evaluate; on a RECEIVED invoice the
    destinatario is the profile holder, whose own NIF is not a question this
    predicate (or this record) needs to answer -- see the module docstring
    for why that is not the same as declaring a received invoice's
    completeness out of scope generally.

    It is meaningful only for a factura simplificada that currently omits the
    tax id -- an ordinaria or rectificativa already requires one
    unconditionally (:mod:`cadrumo.domain.invoices`), and a simplificada that
    already carries one has nothing further to ask for.

    The ``kind`` check is defence in depth rather than the only thing
    preventing a false positive: :class:`~cadrumo.domain.invoices.Invoice`'s
    own class-consistency validator already refuses a RECEIVED SIMPLIFICADA
    with no tax id, so ``counterparty_tax_id is None`` alone already implies
    ``kind is ISSUED`` for every :class:`~cadrumo.domain.invoices.Invoice`
    reachable through normal construction. The check is kept, and tested via
    a bypassed-validation construction, so this function's own contract does
    not silently depend on that domain invariant never changing.

    This is an ADVISORY-weight fact, not a construction-time or verify-time
    refusal: an ordinary domestic ticket with no identified customer is
    common, legitimate practice, and case 3.º's own destinatario-NIF
    requirement is the least certain of the three art. 6.1.d cases this
    codebase can evaluate (it rests on the residency approximation the module
    docstring states, over-strict for a Canarias/Ceuta/Melilla issuer).
    Callers should surface a positive result as a
    :class:`~cadrumo.core.json_contract.Notice`, never as a hard refusal.

    Args:
        invoice: The invoice to evaluate.
        profile: The bucket's taxpayer profile.

    Returns:
        ``True`` when the invoice is a domestic, ISSUED factura simplificada
        with no counterparty tax id, issued by a TAI-established taxpayer.
    """
    if invoice.kind is not InvoiceKind.ISSUED:
        return False
    if invoice.invoice_class is not InvoiceClass.SIMPLIFICADA:
        return False
    if invoice.counterparty_tax_id is not None:
        return False
    if invoice.counterparty_country != _DOMESTIC_COUNTRY_CODE:
        return False
    return issuer_established_in_tai(profile)
