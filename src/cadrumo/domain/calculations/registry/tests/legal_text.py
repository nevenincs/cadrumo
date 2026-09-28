"""Read dates and years out of published legal evidence for tests whose expectation is that text.

The published legal evidence is the normalised text of the cited provision. A test
that asserts a statutory window reads the window from here, so its expectation is
the provision's own wording rather than a year restated by hand.
"""

from __future__ import annotations

import re
from datetime import date

from .published_authority import published_legal_evidence_text, published_legal_reference

_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def spanish_date(day: str, month: str, year: str) -> date:
    """Build a date from the day, Spanish month name and year a provision prints."""
    return date(int(year), _MONTHS[month], int(day))


def legal_text_match(reference_id: str, pattern: str) -> re.Match[str]:
    """Return the first match of ``pattern`` in the published text of one legal citation."""
    text = published_legal_evidence_text(reference_id)
    match = re.search(pattern, text)
    if match is None:
        raise LookupError(f"{reference_id}: the published text does not match {pattern!r}")
    return match


def legal_effective_to(reference_id: str) -> date:
    """Return the last day one closed legal provision is in force."""
    effective_to = published_legal_reference(reference_id).effective_to
    if effective_to is None:
        raise LookupError(f"{reference_id} declares no end of its in-force window")
    return effective_to
