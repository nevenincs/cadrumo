"""Shared label-anchored regex extraction primitive.

Every casilla-complete extractor under :mod:`aeat.adapters.inbound.declaracion`
and :mod:`aeat.adapters.inbound.borrador` runs essentially the same primitive:
for a mapping of ``casilla_id`` to compiled pattern, search the PDF's text
stream and return the first match per casilla. This module is the single
authoritative implementation.

The Spanish amount capture group :data:`SPANISH_AMOUNT_GROUP` is the canonical
AEAT printed-amount format. Extractor modules import it and compose per-casilla
patterns on top of it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ....core.decimal import normalize_decimal_separators
from ....domain.calculations.registry import CasillaId

# AEAT per UNE 82100 uses a non-breaking space (U+00A0)
# or narrow no-break space (U+202F) as the thousands separator —
# NEVER a regular ASCII space (which is reserved for column
# separation). The primitive tolerates those two specific
# code-points between thousand groups via an explicit class.
#
# Narrow/non-breaking space characters do NOT collide with column
# whitespace: the regex uses NBSP and narrow NBSP only (not ASCII
# space/tab), so it stays bounded to the printed amount and cannot
# cross label-to-value gaps that use ASCII space or tab separators.
#
# group was ``(?:\.[0-9]{3})*`` which caused an AEAT
# amount formatted with a non-breaking space ("1\xa0234,56") to be
# silently captured as "234,56" — a 1000x underreport.
SPANISH_AMOUNT_GROUP = r"(-?[0-9]{1,3}(?:[.  ][0-9]{3})*,[0-9]{2})"
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

_WHITESPACE_RE = re.compile(r"\s")


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
    cleaned = _WHITESPACE_RE.sub("", raw).strip()
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


@dataclass(frozen=True)
class LabelHit:
    """One successful label-anchored regex match.

    Attributes:
        casilla_id: Stable casilla identifier the match is bound to.
        raw_value: Verbatim substring captured by group 1 of the pattern,
            with surrounding whitespace stripped.
        decimal_value: ``raw_value`` parsed via :func:`parse_spanish_decimal`,
            or ``None`` when the capture is non-numeric.
        match_count: Number of times the pattern matched ``text``. A value
            greater than ``1`` indicates an ambiguous label and downstream
            consumers should downgrade confidence.
    """

    casilla_id: CasillaId
    raw_value: str
    decimal_value: Decimal | None
    match_count: int


def apply_label_regex(
    text: str,
    label_regex_map: Mapping[CasillaId, re.Pattern[str]],
) -> dict[CasillaId, LabelHit]:
    """Run each ``(casilla_id, pattern)`` regex against ``text``.

    First match wins for the raw value; :attr:`LabelHit.match_count`
    reflects the total number of hits so callers can downgrade confidence
    when the pattern is ambiguous.

    Args:
        text: Concatenated text returned by a PDF parser backend.
        label_regex_map: Mapping of casilla identifier to compiled regex.
            Each pattern must expose group ``1`` as the value capture.

    Returns:
        A dict keyed by casilla identifier, populated only for patterns
        that matched at least once. Each value is a :class:`LabelHit`.
    """
    hits: dict[CasillaId, LabelHit] = {}
    for casilla_id, pattern in label_regex_map.items():
        matches = list(pattern.finditer(text))
        if not matches:
            continue
        first = matches[0]
        raw = first.group(1).strip()
        hits[casilla_id] = LabelHit(
            casilla_id=casilla_id,
            raw_value=raw,
            decimal_value=parse_spanish_decimal(raw),
            match_count=len(matches),
        )
    return hits


__all__ = [
    "SPANISH_AMOUNT_GROUP",
    "TEXT_VALUE_GROUP",
    "LabelHit",
    "apply_label_regex",
    "parse_spanish_decimal",
]
