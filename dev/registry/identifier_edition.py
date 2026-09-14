"""Identify an edition's own qualifier in a registry member identifier."""

from __future__ import annotations

import re
from typing import Final

_YEAR_RANGE: Final = re.compile(r"(?<![0-9])(\d{4})-(\d{4})(?![0-9])")


def edition_token_in_identifier(identifier: str, edition_id: str) -> str | None:
    """Find the edition qualifier without confusing other year ranges with it."""
    if edition_id in identifier:
        return edition_id
    ranged = {year for pair in _YEAR_RANGE.findall(identifier) if "-".join(pair) != edition_id for year in pair}
    segments = set(identifier.replace(":", "-").replace(".", "-").split("-")) - ranged
    matches = [
        segment for segment in edition_id.split("-") if len(segment) == 4 and segment.isdigit() and segment in segments
    ]
    return max(matches, key=len) if matches else None
