"""Validated decimal-string types for the CLI JSON wire.

Monetary magnitudes cross the ``--json`` envelope as strings, because a JSON
number is a float and a float cannot carry a tax amount without rounding it.
Rendering the string is only half the contract: the payload models that
declare those fields were plain ``str``, so a transport row could carry
``"not-decimal"``, ``"NaN"``, ``"Infinity"``, or a negative magnitude that the
canonical :class:`~decimal.Decimal`-typed application models refuse outright.

These annotated types close that gap by validating the rendered text against
the one canonical decimal grammar
(:func:`~core.decimal.try_parse_canonical_decimal`) rather than re-deriving a
per-payload regex. Non-finite values do not conform to that grammar, so
``NaN`` and ``Infinity`` are refused by construction.

The types are plain ``str`` at runtime and on the wire, so adopting one
changes what a payload *accepts*, never what it *emits*.

See Also:
    :func:`~core.decimal.try_parse_canonical_decimal`
        Canonical grammar these types validate against.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from pydantic import AfterValidator

from ...core.decimal.grammar import try_parse_canonical_decimal


def _validate_decimal_wire(value: str, *, signed: bool) -> str:
    """Return ``value`` when it conforms to the canonical decimal grammar."""
    if try_parse_canonical_decimal(value, signed=signed) is None:
        accepted = "a canonical decimal string" if signed else "a non-negative canonical decimal string"
        raise ValueError(
            f"{value!r} is not {accepted}; the accepted form uses a dot decimal separator, "
            "no thousands grouping, no scientific notation, and no NaN/Infinity"
        )
    return value


def _signed(value: str) -> str:
    return _validate_decimal_wire(value, signed=True)


def _non_negative(value: str) -> str:
    return _validate_decimal_wire(value, signed=False)


DecimalWireText = Annotated[str, AfterValidator(_signed)]
"""A decimal magnitude rendered for the JSON wire, sign permitted."""

NonNegativeDecimalWireText = Annotated[str, AfterValidator(_non_negative)]
"""A decimal magnitude rendered for the JSON wire that must not be negative."""


def bounded_decimal_wire_text(
    *,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
    exclusive_minimum: bool = False,
) -> Any:
    """Return a wire-decimal type additionally bounded to a range.

    Canonical models express these bounds on a real
    :class:`~decimal.Decimal` field (``gt=0`` for a movement quantity,
    ``0..100`` for an IVA rate, ``0..1`` for a deductible ratio). The
    transport carries the rendered string, so the same bound has to be
    re-asserted on the text rather than inherited from the field type.

    Args:
        minimum: Lower bound, or ``None`` for unbounded below.
        maximum: Upper bound, or ``None`` for unbounded above.
        exclusive_minimum: When ``True`` the minimum itself is refused,
            matching a canonical ``gt=`` bound rather than ``ge=``.

    Returns:
        An ``Annotated[str, ...]`` type validating the canonical grammar
        and then the range.
    """

    def _check(value: str) -> str:
        parsed = try_parse_canonical_decimal(value, signed=True)
        if parsed is None:
            raise ValueError(
                f"{value!r} is not a canonical decimal string; the accepted form uses a dot decimal "
                "separator, no thousands grouping, no scientific notation, and no NaN/Infinity"
            )
        if minimum is not None:
            if exclusive_minimum and parsed <= minimum:
                raise ValueError(f"{value!r} must be greater than {minimum}")
            if not exclusive_minimum and parsed < minimum:
                raise ValueError(f"{value!r} must not be below {minimum}")
        if maximum is not None and parsed > maximum:
            raise ValueError(f"{value!r} must not exceed {maximum}")
        return value

    return Annotated[str, AfterValidator(_check)]


__all__ = ["DecimalWireText", "NonNegativeDecimalWireText", "bounded_decimal_wire_text"]
