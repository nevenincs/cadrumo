"""Shared label-anchored regex extraction primitive (#305 refactor).

Every casilla-complete extractor under :mod:`aeat.declaracion` and
:mod:`aeat.borrador` runs essentially the same primitive: for a
mapping of ``casilla_id → compiled pattern``, search the PDF's text
stream and return the first match per casilla. This module is the
single authoritative implementation — previously duplicated between
``aeat.declaracion._extract`` and ``aeat.borrador._extract``.

The Spanish amount capture group is the canonical AEAT printed-amount
format. Extractor modules import ``SPANISH_AMOUNT_GROUP`` and
compose per-casilla patterns on top of it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

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
SPANISH_AMOUNT_GROUP = r"(-?[0-9]{1,3}(?:[.  ][0-9]{3})*,[0-9]{2})"  # noqa: RUF001

# Text-value capture — the LAST whitespace-delimited token on the line.
# pdfplumber collapses AEAT's column-separator whitespace to single
# spaces, so the "value-to-the-right-of-the-label" invariant reduces to
# "the final token on the line". Modelos whose values are multi-token
# strings (e.g. "La Rioja" provincia) need a richer bbox-anchored
# primitive tracked under sub-EPIC #305-textual-casillas.
TEXT_VALUE_GROUP = r"(\S+?)\s*$"

_WHITESPACE_RE = re.compile(r"\s")


def parse_spanish_decimal(raw: str) -> Decimal | None:
    """Parse an AEAT-formatted decimal.

    Accepts the canonical Spanish form ``1.234,56``, whitespace-separated
    thousands ``1 234,56`` (any unicode whitespace including U+00A0 NBSP
    and U+202F narrow NBSP — H1), and US-style ``1234.56``.

    Returns ``None`` on unparseable input.
    """
    # Strip every whitespace character (ASCII space, tab, NBSP, narrow NBSP).
    cleaned = _WHITESPACE_RE.sub("", raw).strip()
    if not cleaned or cleaned == "-":
        return None
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


@dataclass(frozen=True)
class LabelHit:
    """One successful label-anchored regex match."""

    casilla_id: str
    raw_value: str
    decimal_value: Decimal | None
    match_count: int
    """Number of times the pattern matched the text; >1 ⇒ ambiguous."""


def apply_label_regex(
    text: str,
    label_regex_map: Mapping[str, re.Pattern[str]],
) -> dict[str, LabelHit]:
    """Run each (casilla_id → pattern) regex against ``text``.

    Returns a dict keyed by casilla ID for every pattern that matched
    at least once. First match wins for the raw value; ``match_count``
    reflects total hits so callers can downgrade confidence on
    ``match_count > 1``.
    """
    hits: dict[str, LabelHit] = {}
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
