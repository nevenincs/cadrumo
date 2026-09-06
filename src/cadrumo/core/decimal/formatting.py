"""Canonical :class:`~decimal.Decimal` formatting helpers for the AEAT domain.

Consolidates the four independent ``_format_decimal`` copies that previously
lived in :mod:`_censo_live`, :mod:`_reconcile`, :mod:`_projection`, and
:mod:`_translator`. All call-sites must import from this module.
"""

from __future__ import annotations

from decimal import Decimal

from ..errors.hierarchy import DecimalFormatError


def format_decimal(
    value: Decimal | None,
    *,
    normalize: bool = False,
    none_value: str | None = None,
) -> str:
    """Render *value* in fixed-point notation (no scientific notation).

    Args:
        value: The decimal to format. Pass ``None`` only when
            *none_value* is also provided.
        normalize: When ``True`` call :meth:`Decimal.normalize` before
            formatting, which strips trailing zeros (e.g.
            ``Decimal("1.50")`` → ``"1.5"``).
        none_value: String to return when *value* is ``None``. When
            ``None`` (the default), a ``None`` *value* raises
            :exc:`DecimalFormatError`.

    Returns:
        Fixed-point string representation of *value*.

    Raises:
        DecimalFormatError: When *value* is ``None`` and *none_value*
            was not provided.

    Examples:
        >>> from decimal import Decimal
        >>> format_decimal(Decimal("12.34"))
        '12.34'
        >>> format_decimal(Decimal("1.50"), normalize=True)
        '1.5'
        >>> format_decimal(None, none_value="0")
        '0'
    """
    if value is None:
        if none_value is None:
            raise DecimalFormatError("format_decimal: value is None but none_value was not provided")
        return none_value

    text = format(value.normalize() if normalize else value, "f")
    # Defensive guard: format(Decimal, "f") should never return an empty
    # string for a valid Decimal, but guard in case of edge-case subclasses.
    return text if text else "0"
