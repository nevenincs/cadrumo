"""Summary-block extraction primitives for Modelo 100.

Thin wrappers re-exporting :data:`aeat.adapters.inbound.pdf._label_regex.SPANISH_AMOUNT_GROUP`
and :func:`aeat.adapters.inbound.pdf._label_regex.parse_spanish_decimal`
while preserving the ``(raw, parsed)`` tuple return shape that the Renta
extractor depends on.
"""

from __future__ import annotations

import re

from ..pdf._label_regex import (
    SPANISH_AMOUNT_GROUP as _SPANISH_AMOUNT_GROUP,
)
from ..pdf._label_regex import (
    parse_spanish_decimal,
)


def apply_label_regex(
    text: str,
    label_regex_map: dict[str, re.Pattern[str]],
) -> dict[str, tuple[str, object]]:
    """Return a ``casilla_id`` to ``(raw, parsed)`` dict for matched patterns.

    Uses :func:`aeat.adapters.inbound.pdf._label_regex.parse_spanish_decimal`
    to coerce the captured group. First match wins for the raw value;
    callers detect ambiguity via ``pattern.findall(text)`` if they want
    to downgrade confidence.

    Args:
        text: The full text to search.
        label_regex_map: Mapping of casilla id to a compiled
            :class:`re.Pattern` whose first capture group is the raw
            Spanish-formatted amount.

    Returns:
        Dict keyed by casilla id whose value is a ``(raw, parsed)``
        tuple where ``parsed`` is a :class:`decimal.Decimal` when
        parseable and the original raw string otherwise.
    """
    hits: dict[str, tuple[str, object]] = {}
    for casilla_id, pattern in label_regex_map.items():
        match = pattern.search(text)
        if match is None:
            continue
        raw = match.group(1).strip()
        hits[casilla_id] = (raw, parse_spanish_decimal(raw))
    return hits


__all__ = ["_SPANISH_AMOUNT_GROUP", "apply_label_regex"]
