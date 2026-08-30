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

from typing import Final

from ...core.identity import IdentityError, validate_spanish_tax_id
from .establishment import country_code_for_printed_tax_identifier
from .schema import EUMemberState

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
        return _spanish_identification(printed_identifier)
    try:
        return EUMemberState(code.lower())
    except ValueError:
        # A prefix naming a country outside the rate-schedule catalogue states a
        # registration this fact's closed type cannot carry. Unestablished is
        # the honest answer; inventing a member would be worse than silence.
        return None


_SPANISH_IVA_PREFIX: Final[str] = "ES"
"""The prefix RGAT art. 25 puts in front of a Spanish NIF-IVA.

Declared here rather than borrowed from the establishment vocabulary, because
that vocabulary deliberately does not carry it and must not start to.
"""


def _spanish_identification(printed_identifier: str | None) -> EUMemberState | None:
    """Return Spain when the printed number is an ES-prefixed Spanish identifier.

    The other half of an axis that was one-sided. Every sibling prefix is
    recognised by matching the number's BODY against the structure its prefix
    claims, and Spanish identifiers are checksum identifiers rather than
    structural ones -- so ``ES`` could not join the vocabulary the way its
    siblings did, and the filer's own identification stayed merely assertable
    while a counterparty's was established from the paper.

    RGAT art. 25 is what makes the printed form readable: for a party in the
    Registro de operadores intracomunitarios the identifier is the ordinary one
    "al que se antepondrá el prefijo ES, conforme al estándar internacional
    código ISO-3166 alfa 2". So the prefix is regulated rather than conventional,
    and the body is validated by the shipped AEAT control-letter algorithm
    instead of by a structural pattern.

    **This cannot leak a Spanish ESTABLISHMENT, and that is structural rather
    than careful.** It is reached only where the establishment resolver already
    returned nothing, it returns an IDENTIFICATION state, and the establishment
    ladder reads the country code -- which stays empty for Spain by design,
    because registration is not establishment. A bare Spanish CIF with no prefix
    is likewise untouched: it prints no prefix, so it states no identification,
    and reading absence as a Spanish one would manufacture the fact from silence.
    """
    if printed_identifier is None:
        return None
    compact = "".join(printed_identifier.split()).replace("-", "").replace(".", "").upper()
    if not compact.startswith(_SPANISH_IVA_PREFIX):
        return None
    try:
        validate_spanish_tax_id(compact[len(_SPANISH_IVA_PREFIX) :])
    except IdentityError:
        # An ES prefix over a body that fails the control letter is not a
        # Spanish identification; it is a misread or a different country's
        # number wearing the wrong prefix. Silence is the honest answer.
        return None
    return EUMemberState.ES
