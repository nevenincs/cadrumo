"""Summary-block extraction primitives for Modelo 100 (#305 cluster F).

Thin wrappers re-exporting the shared primitive from
:mod:`aeat._pdf_import._label_regex` while keeping the original
``(raw, parsed)`` tuple return shape the Renta extractor depends on.
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
    """Return a ``casilla_id → (raw, parsed)`` dict for matched patterns.

    Uses the shared ``parse_spanish_decimal`` from
    :mod:`aeat._pdf_import._label_regex`. First match wins for the raw
    value; callers detect ambiguity via ``pattern.findall(text)`` if
    they want to downgrade confidence.
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
