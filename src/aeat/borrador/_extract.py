"""Summary-block extraction primitives for Modelo 100 (#305 cluster F)."""

from __future__ import annotations

import re

from ..declaracion._extract import parse_spanish_decimal

_SPANISH_AMOUNT_GROUP = r"(-?[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})"


def apply_label_regex(
    text: str,
    label_regex_map: dict[str, re.Pattern[str]],
) -> dict[str, tuple[str, object]]:
    """Apply each (casilla_id → pattern) regex to ``text``.

    Returns a dict ``casilla_id → (raw_capture, parsed_decimal)`` for
    every pattern that matched at least once. First match wins; callers
    detect ambiguity via ``pattern.findall(text)`` if they want to
    downgrade confidence.
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
