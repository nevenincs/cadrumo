"""Shared Decimal formatting primitive for the financial subpackage."""

from __future__ import annotations

from decimal import Decimal


def canonical_decimal(value: Decimal) -> str:
    """Render a ``Decimal`` as a stable fixed-point string.

    Zero renders as ``"0"`` regardless of input precision. Non-zero values
    are normalized (trailing zeros removed) and formatted without exponent
    notation. This shape is safe to feed into stable hash inputs and is
    the single source of truth for decimal rendering in the financial
    subpackage.

    Args:
        value: Decimal to render.

    Returns:
        A fixed-point string representation.
    """
    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")


__all__ = ["canonical_decimal"]
