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

Two adapters read AEAT-printed money, and they sit on opposite sides of the
hexagon: the inbound sanción/liquidación notification reader and the outbound
sede IVA compensation wallet reader. Neither may own a primitive the other
imports, so the grammar belongs to neither and is declared here, beside the
separator and coercion helpers both already consume.

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

_AEAT_PRINTED_MONEY_RE: Final[re.Pattern[str]] = re.compile(r"^-?\d{1,3}(?:\.\d{3})*,\d{2}$|^-?\d+,\d{2}$")


def is_aeat_printed_money(text: str) -> bool:
    """Return whether *text* is exactly one AEAT-printed monetary amount.

    The token must BE the shape end to end. Grouped (``3.687,12``) and
    ungrouped (``1234,56``) renderings both conform, with or without a leading
    ``-``; a missing two-decimal comma tail does not.

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
        >>> is_aeat_printed_money("1.843")
        False
        >>> is_aeat_printed_money("total 3.687,12 euros")
        False
    """
    return _AEAT_PRINTED_MONEY_RE.match(text) is not None
