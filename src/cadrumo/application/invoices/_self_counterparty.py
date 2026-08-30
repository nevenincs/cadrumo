"""Whether an invoice names the taxpayer running this app as its own counterparty.

An invoice records an operation between two parties. When the recorded
counterparty is the filer themselves, the record does not describe a real
operation in either direction: a received invoice would mean buying from
oneself, an issued one selling to oneself. Neither is a transaction the tax
system recognises as between parties, and both are conspicuous -- the
counterparty totals on Modelo 347 and Modelo 349 are informativas AEAT
cross-checks against what the *counterparty* declared, so a self-dealing row
is matched against the filer's own return.

This lives in the application layer for the same reason
:mod:`~application.invoices._issuer_establishment` does: it is a fact about the
TAXPAYER, not about the invoice, and :class:`~domain.invoices.Invoice` is a pure
domain record that does not reach into profile state.

The failure this guards is not hypothetical or operator-typo-shaped, and the
mechanism has changed while the exposure has not. The reader no longer scans for
the first checksum-valid Spanish tax id, and the field contract
(:data:`~llm.invoice_field_contract.INVOICE_FIELD_CONTRACTS`) no longer asks only for "the supplier's
NIF/NIE/CIF": both parties are asked for separately, by role, precisely because
one identifier plus a caller's assumption made the two indistinguishable.

What survives that fix is the ISSUED case, and it survives by construction
rather than by defect. On an invoice the filer issued, the supplier slot
legitimately holds the filer's OWN identifier -- the document is correct and the
reading is correct -- so any path that takes the supplier side as the
counterparty records the taxpayer against themselves. The value is real,
checksum-valid, and bound for an informativa AEAT reconciles against the
counterparty's own return. A probabilistic reader transposing the two roles on
an ambiguous layout reaches the same place by a different route.

Scope note, stated rather than assumed: this treats a self-naming counterparty
as always wrong, which holds for every operation this codebase can currently
record. Autoconsumo (LIVA art. 9) is the one family where a taxpayer documents
an operation directed at themselves, and it has no
:class:`~domain.iva.IvaCategory` member here -- the only trace is the
:attr:`~core.Art104TresExclusion.SELF_SUPPLY_ART_9_1_D` prorrata exclusion, which is declared
"auto-derived from the IVA category" against a category that does not exist. If
autoconsumo invoicing is ever modelled, THIS is the predicate that must learn
about it; until then a self-naming counterparty is a misread, not a self-supply.

See Also:
    :func:`~application.invoices.issuer_established_in_tai`
        Sibling profile-derived invoice predicate.
    :class:`~domain.deadlines.TaxpayerProfile`
        Owns the per-taxpayer identity fact; one profile per bucket.
"""

from __future__ import annotations

from ...core.identity import same_tax_identifier
from ...domain.deadlines import TaxpayerProfile

__all__ = ["counterparty_is_the_filer"]


def counterparty_is_the_filer(*, counterparty_tax_id: str | None, profile: TaxpayerProfile) -> bool:
    """Return whether ``counterparty_tax_id`` names the taxpayer in ``profile``.

    Compares on :func:`~core.identity.same_tax_identifier`, the one shared
    "these name the same bearer" predicate -- the same one the evidence reader's
    own-identity exclusion consumes, so a document that evades one cannot evade
    the other. That helper deliberately asserts no checksum, which is right
    here: the question is identity, not validity, and a profile carrying a
    foreign or otherwise non-Spanish identifier must still be comparable against
    a document that prints it.

    Args:
        counterparty_tax_id: The counterparty identifier about to be recorded,
            or ``None`` when the invoice carries none (a factura simplificada
            may legitimately omit it).
        profile: The bucket's :class:`TaxpayerProfile`.

    Returns:
        ``True`` only when both sides carry a value and they are the same
        identifier. An absent counterparty id, or a profile with no tax id,
        answers ``False`` -- absence is not a match, and this predicate must not
        turn "nothing to compare" into "the same".
    """
    return same_tax_identifier(counterparty_tax_id, profile.tax_id)
