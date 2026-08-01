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

from typing import Annotated

from pydantic import AfterValidator

from ...core.decimal import try_parse_canonical_decimal


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

__all__ = ["DecimalWireText", "NonNegativeDecimalWireText"]
