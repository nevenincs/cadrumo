"""Resolve which Member State a party is IVA-identified in — never where it is established.

Separate from :mod:`._establishment` because the two answer legally distinct
questions, and conflating them is the defect this module exists to end. A
document printing ``DE811234567`` states two things that look like one: that the
party operates under a German IVA identification, and — the reader's inference —
that the party is in Germany. Only the first is evidence.

**Registration IS the identification fact, so a printed prefix is decisive
here.** Where :mod:`._establishment` refuses to let the same prefix settle a
place on its own -- the establishment ladder reaches a territory only once a
printed country name or postal code corroborates one -- this module treats it as
what it actually is: the Member State under whose identification the party
operates, stated by the party itself on its own invoice. There is nothing to
corroborate, because nothing further is being claimed.

**And it establishes NOTHING about establishment, symmetrically on both sides.**
Every Member State registers non-residents on the same terms Spain does, so a
German number is exactly as compatible with a *sede de actividad económica* in
Spain as a Spanish ``N``-leader CIF is with one in Germany (Ley 37/1992
arts. 69–70). The asymmetry that made a foreign prefix decisive for place while
a Spanish one was correctly refused is closed by splitting the fact, not by
demanding corroboration on one side of it.

**Spain cannot arise from a printed IVA number here**, and that is a property of
the prefix vocabulary rather than a judgement made in this module: Spanish
identifiers are checksum identifiers routed through the Spanish tax-id validator
and ``ES`` is absent from :class:`~core.identity.NifIvaPrefix`. A Spanish
identification is therefore established from the Spanish identifier authority or
declared, never inferred here.

**That absence is an implementation boundary, not a statement that the evidence
does not exist.** This path recognises a prefix by matching the number's body
against the structural pattern its own prefix claims, and a Spanish identifier is
validated by the AEAT control-letter checksum instead -- so ``ES`` could not join
the vocabulary as a pattern the way its siblings did. Whether it SHOULD join,
through the checksum validator this codebase already ships, is an open scope
question about the axis rather than a settled refusal, and the earlier wording
here read as the latter.

See Also:
    :class:`~domain.iva.IvaTerritorialScope`
        The OTHER party fact — where the party is established. A value here
        never implies one there.
    :class:`~domain.iva.PartyFact`
        The closed pair, and the axis a classification branch declares it
        consumes.
"""

from __future__ import annotations

from ._establishment import country_code_for_printed_tax_identifier
from ._schema import EUMemberState

__all__ = ["identification_state_for_printed_tax_identifier"]


def identification_state_for_printed_tax_identifier(
    printed_identifier: str | None,
) -> EUMemberState | None:
    """Return the Member State a printed IVA number identifies the party in.

    A composition rather than a second rule set:
    :func:`._establishment.country_code_for_printed_tax_identifier` stays the
    single authority on which country a printed number NAMES — including the
    Greek ``EL``/``GR`` divergence and the requirement that the number's body
    match the structure its own prefix claims — and this adds only the step from
    that ISO code to the closed catalogue.

    Args:
        printed_identifier: The identifier as transcribed, or ``None``.

    Returns:
        The :class:`~domain.iva.EUMemberState` the number identifies the party
        in, or ``None`` when no IVA number was recognised.

        ``None`` means the identification was not established, never that the
        party is identified nowhere and above all never that it is identified in
        Spain: a document printing a bare Spanish ``B``-CIF prints no prefix at
        all, so reading absence as a Spanish identification would manufacture
        the fact from its own silence.
    """
    code = country_code_for_printed_tax_identifier(printed_identifier)
    if code is None:
        return None
    try:
        return EUMemberState(code.lower())
    except ValueError:
        # A prefix naming a country outside the rate-schedule catalogue states a
        # registration this fact's closed type cannot carry. Unestablished is
        # the honest answer; inventing a member would be worse than silence.
        return None
