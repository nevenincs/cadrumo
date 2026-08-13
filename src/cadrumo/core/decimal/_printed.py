"""Anchored shape check for AEAT's own printed-money rendering.

AEAT prints a monetary figure to one house convention: an optional sign,
thousands grouped in threes, and a **mandatory two-decimal comma tail**. This
module owns the single anchored grammar for that convention.

It is a *shape* check, not a parser. It answers whether a token **is** an
AEAT-printed amount end to end — never merely whether it contains one — and the
callers that consult it run it as a gate before handing the token to a parser.

Why the two-decimal tail is mandatory
-------------------------------------

The tail is the whole point of the check. A template that began printing whole
euros would render ``1.843``, and a permissive read resolves that to either
``1843`` or ``1.843`` with nothing in the token to choose by — a thousandfold
error on a figure a taxpayer pays or appeals against. Requiring the comma tail
means such a template change surfaces as the refusal it is, instead of being
silently reinterpreted as a thousands-grouped integer.

This is the same ambiguity :func:`european_thousands_reading_is_ambiguous`
refuses for hand-typed text, closed here from the other side: that predicate
detects the missing evidence, this grammar demands the evidence be present.

Why it lives in ``core``
------------------------

The strict and the tolerant readings of a printed amount are one taxonomy, not
two neighbouring conveniences. Which grammar a token is judged by follows from
its provenance — AEAT printed it, or a human typed it — and that choice has to
be made identically wherever an amount enters the system. A taxonomy whose
members are decided together belongs where the whole tree can reach it, beside
the separator and coercion helpers its callers already consume.

Its readers happen to be an inbound adapter (the sanción/liquidación
notification reader) and an outbound one (the sede IVA compensation wallet
reader). That is not itself the argument for the placement: this tree already
carries a runtime outbound-to-inbound adapter edge, so "an adapter may not own
a primitive its counterpart imports" would be a rule stated here and broken
elsewhere. The grammar lives in ``core`` because of what it is, not because of
who could not otherwise import it.

The check previously shipped as a hand-copied regex literal in each of those
two modules — one of which described it in prose as "shared verbatim", which is
precisely what a duplicate looks like from the inside.

Relationship to the sibling grammars
------------------------------------

:func:`try_parse_canonical_decimal` owns the *hand-typed* dot-decimal grammar;
this module owns the *AEAT-printed* comma-tailed one. Pick by provenance.

:data:`~adapters.inbound.pdf.SPANISH_AMOUNT_GROUP` is the UNANCHORED capture
group for this same convention, used to FIND an amount inside a longer printed
line. The two are deliberately **not** interchangeable: anchoring that capture
group would refuse an ungrouped ``1234,56``, which this grammar accepts.
"""

from __future__ import annotations

import re
from typing import Final

# Spelled with escapes rather than literal code points: a non-breaking space
# and a narrow no-break space are invisible in a diff, in a review and in an
# editor, so a literal one is silently corruptible by anything that
# normalises whitespace.
AEAT_THOUSANDS_SEPARATORS: Final[str] = ".\u00a0\u202f"
"""The code points AEAT prints between thousand groups: ``.``, NBSP, narrow NBSP.

Per UNE 82100, AEAT groups thousands with a full stop, a non-breaking space
(U+00A0) or a narrow no-break space (U+202F) — and **never a plain ASCII
space**, which is reserved for column separation. That distinction is the whole
value of naming the set: admitting ASCII space would let a grammar walk across
the gap between a label and its value and read two adjacent numbers as one.

Declared here so the anchored grammar in this module and the unanchored capture
group :data:`~adapters.inbound.pdf.SPANISH_AMOUNT_GROUP` cannot drift on which
code points AEAT actually prints. They differ on anchoring, deliberately; they
must not differ on this.
"""

_SEPARATOR_CLASS: Final[str] = f"[{re.escape(AEAT_THOUSANDS_SEPARATORS)}]"

_AEAT_PRINTED_MONEY_RE: Final[re.Pattern[str]] = re.compile(
    r"^-?\d{1,3}(?:" + _SEPARATOR_CLASS + r"\d{3})*,\d{2}$|^-?\d+,\d{2}$",
)


def is_aeat_printed_money(text: str) -> bool:
    r"""Return whether *text* is exactly one AEAT-printed monetary amount.

    The token must BE the shape end to end. Grouped (``3.687,12``, and the
    non-breaking-space renderings of the same figure) and ungrouped
    (``1234,56``) forms both conform, with or without a leading ``-``; a
    missing or wrong-width two-decimal comma tail does not, and neither does a
    thousands group separated by a plain ASCII space.

    Args:
        text: The candidate token, already stripped of any currency unit,
            tabulation filler and surrounding whitespace by the caller.

    Returns:
        ``True`` when *text* conforms to the AEAT printed-money grammar.

    Examples:
        >>> is_aeat_printed_money("3.687,12")
        True
        >>> is_aeat_printed_money("1234,56")
        True
        >>> is_aeat_printed_money("-1.234,56")
        True
        >>> is_aeat_printed_money("1\u00a0234,56")
        True
        >>> is_aeat_printed_money("1 234,56")
        False
        >>> is_aeat_printed_money("1.843")
        False
        >>> is_aeat_printed_money("total 3.687,12 euros")
        False
    """
    # fullmatch, not match: ``$`` also matches immediately before a trailing
    # newline, so ``match`` would accept "3.687,12\n" as the shape. Every
    # caller strips first, but a grammar that is anchored by name should not
    # depend on the caller having done so.
    return _AEAT_PRINTED_MONEY_RE.fullmatch(text) is not None
