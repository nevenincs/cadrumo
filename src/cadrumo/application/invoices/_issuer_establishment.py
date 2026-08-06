"""Whether the taxpayer issuing an invoice is established in the TAI.

RD 1619/2012 art. 6.1.d makes a factura simplificada's counterparty tax id
mandatory in three cases, and the third is a fact about the issuer -- this
app's own taxpayer, never the invoice's counterparty -- rather than about the
invoice itself: "operaciones que se entiendan realizadas en el territorio de
aplicación del impuesto [TAI] y el empresario o profesional obligado a la
expedición de la factura haya de considerarse establecido en dicho
territorio."

:class:`~cadrumo.domain.invoices.Invoice` has nowhere to carry this -- it is
a pure domain record with no profile dependency, by design (a domain model
does not reach into repository/profile state) -- and it is not a NEW fact
this app needs to learn: :class:`~cadrumo.domain.deadlines.TaxpayerProfile`
already carries :attr:`~cadrumo.domain.deadlines.TaxpayerProfile.fiscal_residency`
(TRLIRNR RDLeg 5/2004 art. 2), which this module reads rather than
duplicating.

**The approximation, stated rather than hidden.** ``RESIDENT_IRPF`` is
establishment in the TAI for essentially every real user of this app (a
Spanish-resident autónomo or professional). ``NON_RESIDENT_IRNR`` is treated
as NOT established -- correct for the overwhelming majority of non-resident
taxpayers, but not for the narrow case of a non-resident operating through a
Spanish permanent establecimiento permanente, which this codebase does not
model as its own axis anywhere yet. A future ``EstablecimientoPermanente``
concept would need to override this predicate for that carve-out; until then
this module states the approximation rather than a guess dressed as
certainty.

See Also:
    :class:`cadrumo.domain.deadlines.FiscalResidency`
        The two-member closed enum this predicate reads.
    :class:`cadrumo.domain.deadlines.TaxpayerProfile`
        Owns the per-taxpayer residency fact; one profile per bucket.
"""

from __future__ import annotations

from ...domain.deadlines import FiscalResidency, TaxpayerProfile
from ...domain.invoices import Invoice, InvoiceClass

_DOMESTIC_COUNTRY_CODE = "ES"

__all__ = ["issuer_established_in_tai", "simplificada_requires_tax_id_for_domestic_issuer"]


def issuer_established_in_tai(profile: TaxpayerProfile) -> bool:
    """Return whether the taxpayer issuing invoices under ``profile`` is established in the TAI.

    ``fiscal_residency is None`` is treated as ``RESIDENT_IRPF``, matching
    the field's own documented default for engine consumers
    (:attr:`~cadrumo.domain.deadlines.TaxpayerProfile.fiscal_residency`).

    Args:
        profile: The bucket's taxpayer profile.

    Returns:
        ``True`` unless the profile declares ``NON_RESIDENT_IRNR``. See the
        module docstring for the non-resident-with-permanent-establishment
        carve-out this predicate does not yet model.
    """
    return profile.fiscal_residency is not FiscalResidency.NON_RESIDENT_IRNR


def simplificada_requires_tax_id_for_domestic_issuer(invoice: Invoice, profile: TaxpayerProfile) -> bool:
    """Return whether RD 1619/2012 art. 6.1.d case 3.º makes ``invoice`` need a tax id.

    Case 3.º applies to a domestic operation (``counterparty_country ==
    "ES"``) whose issuer is established in the TAI. It is meaningful only for
    a factura simplificada that currently omits the tax id -- an ordinaria or
    rectificativa already requires one unconditionally
    (:mod:`cadrumo.domain.invoices`), and a simplificada that already carries
    one has nothing further to ask for.

    This is an ADVISORY-weight fact, not a construction-time or verify-time
    refusal: an ordinary domestic ticket with no identified customer is
    common, legitimate practice, and case 3.º's own destinatario-NIF
    requirement is the least certain of the three art. 6.1.d cases this
    codebase can evaluate (it rests on the residency approximation the module
    docstring states). Callers should surface a positive result as a
    :class:`~cadrumo.core.json_contract.Notice`, never as a hard refusal.

    Args:
        invoice: The invoice to evaluate.
        profile: The bucket's taxpayer profile.

    Returns:
        ``True`` when the invoice is a domestic factura simplificada with no
        counterparty tax id, issued by a TAI-established taxpayer.
    """
    if invoice.invoice_class is not InvoiceClass.SIMPLIFICADA:
        return False
    if invoice.counterparty_tax_id is not None:
        return False
    if invoice.counterparty_country != _DOMESTIC_COUNTRY_CODE:
        return False
    return issuer_established_in_tai(profile)
