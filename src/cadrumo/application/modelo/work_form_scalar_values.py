"""Scalar comparison and zero semantics for modelo work forms."""

from datetime import date
from decimal import Decimal

from .edit_apply_scalar_contracts import ModeloEditWireScalar, wire_scalar_value


def holds_zero(value: Decimal | int | str | bool | date | None) -> bool:
    """Whether a held amount is exactly zero, distinct from an absent value."""
    return isinstance(value, Decimal | int) and not isinstance(value, bool) and value == 0


def comparable_entry(value: Decimal | int | str | bool | date | None) -> ModeloEditWireScalar:
    """Compare numeric entries by value while preserving other wire scalars.

    Decimal trailing zeros do not distinguish entries. Booleans compare as
    the numeric figure carried by their channel; other values stay as written.
    """
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return None if value is None else wire_scalar_value(value)
