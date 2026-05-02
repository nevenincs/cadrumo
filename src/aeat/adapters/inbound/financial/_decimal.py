"""Canonical :class:`decimal.Decimal` rendering primitive for the financial subpackage.

This module exposes a single helper, :func:`canonical_decimal`, used wherever a
financial amount must be turned into a stable string — for example, when
constructing the inputs to a deterministic transaction-id hash. Centralising
the rule here ensures every provider and downstream consumer renders amounts
the same way.
"""

from __future__ import annotations

from decimal import Decimal


def canonical_decimal(value: Decimal) -> str:
    """Render a :class:`decimal.Decimal` as a stable fixed-point string.

    Zero renders as ``"0"`` regardless of input precision. Non-zero values are
    normalised (trailing zeros removed) and formatted without exponent
    notation. The output is safe to feed into stable hash inputs and is the
    single source of truth for decimal rendering across the financial
    subpackage.

    Args:
        value: Decimal to render.

    Returns:
        Fixed-point string representation.

    Examples:
        >>> from decimal import Decimal
        >>> canonical_decimal(Decimal("0.00"))
        '0'
        >>> canonical_decimal(Decimal("1.50"))
        '1.5'
    """
    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")


__all__ = ["canonical_decimal"]
