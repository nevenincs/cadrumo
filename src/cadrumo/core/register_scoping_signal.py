"""Closed axis for what an offered option list SUGGESTS about its own scoping.

One enum, and every member name begins with a hedge on purpose. Whether the
declaraciones register's combobox option lists are scoped to the authenticated
NIF or are a static universal catalogue cannot be settled without an authorised
live probe against an account with real filing history. This enum does not settle
it; it records what a free, offline comparison SUGGESTS, and it is deliberately
incapable of expressing a resolved answer.

See :class:`RegisterScopingSignal`.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "RegisterScopingSignal",
]


class RegisterScopingSignal(StrEnum):
    """What an offered modelo set suggests about whether it is NIF-scoped.

    There is deliberately NO ``UNIVERSAL`` and NO ``NIF_SCOPED`` member, and the
    absent pair is the point. A resolved member would let a heuristic reading be
    stored, exported and later cited as though a live probe had confirmed it —
    and the whole design rests on never making that claim. Every member is a
    hedge, so a consumer cannot accidentally render this as settled.

    Nothing in the walk grid depends on this classification: the offered option
    set is unioned in additively regardless, so a reading here can never widen or
    narrow what is walked. It exists to tell an operator, and a future reviewer,
    which way the free evidence points.

    Attributes:
        LIKELY_UNIVERSAL: The offered set includes modelos the taxpayer's own
            declared facts positively EXCLUDE. A list scoped to this NIF would
            not offer a modelo the profile answers "no" for, so the list looks
            like a catalogue rendered regardless of taxpayer. This is the reading
            that matters most, because it is the one under which measuring
            coverage against the offered set alone would be meaningless.
        LIKELY_NIF_SCOPED: The offered set includes NONE of the modelos the
            profile positively excludes. Consistent with a NIF-scoped list, but
            only consistent with it: a universal catalogue would produce the same
            observation for a taxpayer whose profile excludes nothing the
            register happens to list.
        INCONCLUSIVE: The comparison cannot discriminate — there were no
            confidently-excluded modelos to look for, or no offered modelos to
            look in. Never a weak version of either reading above; it means the
            available evidence says nothing either way.
    """

    LIKELY_UNIVERSAL = "likely_universal"
    LIKELY_NIF_SCOPED = "likely_nif_scoped"
    INCONCLUSIVE = "inconclusive"
