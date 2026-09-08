"""Shared label-anchored regex and decimal parsing primitives.

The casilla-complete parser under :mod:`adapters.inbound.declaracion` owns
target dispatch, page provenance, and missing, malformed, and ambiguous result
classification. This module supplies only the reusable regex fragments and
printed-decimal parser those extraction paths compose.

The Spanish amount capture group :data:`SPANISH_AMOUNT_GROUP` is the canonical
AEAT printed-amount format. Extractor modules import it and compose per-casilla
patterns on top of it.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from ....core.decimal.coercion import normalize_decimal_separators
from ....core.decimal.printed_money import AEAT_THOUSANDS_SEPARATORS

# The thousands-separator class is NOT declared here: it is
# :data:`~core.decimal.AEAT_THOUSANDS_SEPARATORS`, shared with the anchored
# grammar in that module so the two cannot disagree on which code points AEAT
# prints. Per UNE 82100 those are ``.``, U+00A0 NBSP and U+202F narrow NBSP --
# never a plain ASCII space or tab, which are AEAT's column separators. That
# exclusion is what keeps this pattern from crossing a label-to-value gap.
#
# The group was once ``(?:\.[0-9]{3})*``, which caused an AEAT amount formatted
# with a non-breaking space ("1 234,56") to be silently captured as
# "234,56" -- a 1000x underreport.
SPANISH_AMOUNT_GROUP = r"(-?[0-9]{1,3}(?:[" + re.escape(AEAT_THOUSANDS_SEPARATORS) + r"][0-9]{3})*,[0-9]{2})"
"""Capture group for AEAT-printed monetary amounts (Spanish locale).

Matches optional sign, 1-3 leading digits, zero or more groups of
``<thousands-separator><3 digits>`` where the separator is ``.`` (ASCII
full stop), U+00A0 NBSP, or U+202F narrow NBSP, and a mandatory
``,<2 digits>`` decimal tail. The separator class deliberately excludes
ASCII space and tab so the regex cannot cross AEAT column-separator
whitespace.
"""

# Text-value capture — the LAST whitespace-delimited token on the line.
# pdfplumber collapses AEAT's column-separator whitespace to single
# spaces, so the "value-to-the-right-of-the-label" invariant reduces to
# "the final token on the line". Modelos whose values are multi-token
# strings (e.g. "La Rioja" provincia) need a richer bbox-anchored
# primitive instead.
TEXT_VALUE_GROUP = r"(\S+?)\s*$"
"""Capture group for the last whitespace-delimited token on a line.

pdfplumber collapses AEAT's column-separator whitespace to single spaces, so
the "value-to-the-right-of-the-label" invariant reduces to "the final token
on the line". Multi-token textual values (e.g. ``"La Rioja"``) need a
richer bbox-anchored primitive instead.
"""

# AEAT serves the SAME receipt template in Spanish or English depending on the
# sede UI language the filer used, so the label printed beside the presentador's
# NIF is render-dependent while the value beside it is not. Both inbound receipt
# adapters must therefore anchor on either rendering, and they anchor on this one
# fragment so a newly-observed rendering is added in a single place.
#
# pdfplumber lifts the English label with no spaces around the parenthetical
# ("Tax identification number(NIF)of filer:"), so every internal separator is
# optional. The trailing "of filer" is optional too: it is present on the
# value-then-label column layout and absent from some flat renderings.
#
# This fragment matches the LABEL only. It deliberately carries no value class,
# so composing patterns keep their own tax-id shape constraint — widening the
# accepted renderings must never widen the accepted NIF.
PRESENTADOR_NIF_LABEL = r"(?:NIF(?:\s*Presentador)?|Tax\s*identification\s*number\s*\(\s*NIF\s*\)(?:\s*of\s*filer)?)"
"""Non-capturing alternation of AEAT's Spanish and English presentador-NIF labels.

Matches ``NIF``, ``NIF Presentador``, and the English-render
``Tax identification number(NIF)of filer`` (with or without the trailing
``of filer``, and tolerant of pdfplumber's missing separators around the
parenthetical). Carries no capture group and no tax-id value class, so a caller
composes it with its own value pattern and separator expectations.
"""

# The same Spanish/English render split applies to the two header stamps that
# identify WHICH filing a receipt is: the form code and the tax year. An
# English-render receipt prints "FORM 390" and "Financial year 2021" where the
# Spanish one prints "Modelo 390" and "Ejercicio 2021".
MODELO_LABEL = r"(?:Modelo|Form)"
"""Non-capturing alternation of AEAT's Spanish and English form-code labels."""

EJERCICIO_LABEL = r"(?:Ejercicio|Financial\s*year)"
"""Non-capturing alternation of AEAT's Spanish and English tax-year labels."""

#: A single whitespace character, DELETED rather than collapsed: a PDF label
#: is matched with its spacing removed entirely. Named for that operation so
#: it no longer collides with the run-collapsing pattern three other modules
#: used under the name ``_WHITESPACE_RE``.
_WHITESPACE_TO_DELETE_RE = re.compile(r"\s")


def parse_spanish_decimal(raw: str) -> Decimal | None:
    """Parse an AEAT-formatted decimal string into a :class:`decimal.Decimal`.

    Accepts the canonical Spanish form ``1.234,56``, whitespace-separated
    thousands ``1 234,56`` (any unicode whitespace including U+00A0 NBSP
    and U+202F narrow NBSP), and US-style ``1234.56``. The parser is
    intentionally more permissive than the regex capture in
    :data:`SPANISH_AMOUNT_GROUP` so it can recover values from messy input
    that has already been delimited by an upstream label match.

    Args:
        raw: Raw numeric substring captured from the PDF.

    Returns:
        The parsed value, or ``None`` if ``raw`` is empty, a bare sign, or
        otherwise unparseable.
    """
    # Strip every whitespace character (ASCII space, tab, NBSP, narrow NBSP).
    cleaned = _WHITESPACE_TO_DELETE_RE.sub("", raw).strip()
    if not cleaned or cleaned == "-":
        return None
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = normalize_decimal_separators(cleaned, strip_thousands=True)
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = normalize_decimal_separators(cleaned, strip_thousands=False)
    try:
        parsed = Decimal(cleaned)
    except InvalidOperation:
        return None
    # Reject non-finite poison values (NaN, sNaN, ±Infinity). Decimal accepts
    # these literals without raising InvalidOperation, but they cannot feed
    # the AEAT decimal pipeline (arithmetic propagates the special value,
    # comparisons silently fail, and serialised filing payloads would emit
    # invalid digits).
    if not parsed.is_finite():
        return None
    return parsed


__all__ = [
    "SPANISH_AMOUNT_GROUP",
    "TEXT_VALUE_GROUP",
    "parse_spanish_decimal",
]
