"""Strict numeric coercion for fixed-width tax-return wire fields."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_FIXED_WIDTH_DECIMAL_RE = re.compile(r"^-?[0-9]+(?:\.[0-9]+)?$")


def coerce_fixed_width_decimal(value: object) -> Decimal:
    """Return a finite exact decimal without guessing or lossy float conversion.

    Fixed-width filing values are already typed application values or canonical
    machine-authored strings.  Whitespace, exponent notation, leading plus,
    booleans, and binary floats are therefore refusals rather than alternate
    spellings.
    """
    if isinstance(value, (bool, float)):
        raise ValueError("fixed-width numeric values cannot be boolean or float")
    if isinstance(value, Decimal):
        parsed = value
    elif isinstance(value, int):
        parsed = Decimal(value)
    elif isinstance(value, str) and _FIXED_WIDTH_DECIMAL_RE.fullmatch(value) is not None:
        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("fixed-width numeric value is not a decimal") from exc
    else:
        raise ValueError("fixed-width numeric value must be an int, Decimal, or canonical decimal string")
    if not parsed.is_finite():
        raise ValueError("fixed-width numeric value must be finite")
    return parsed


__all__ = ["coerce_fixed_width_decimal"]
