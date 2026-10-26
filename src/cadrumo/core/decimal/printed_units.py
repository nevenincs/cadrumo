"""Removal of the currency UNIT a document prints beside an amount.

A printed amount carries its unit: ``1.200,00 €``, ``EUR 1200.00``,
``1200.00 EUR``. The unit is not a digit, so a reader that copies the printed
form faithfully hands the decimal authority a string it must refuse, and the
field is lost for having been read too literally. This module owns the one rule
that separates the unit from the number.

It lives in ``core`` because both halves of the extraction contract need it and
they sit on opposite sides of the dependency direction: the reading adapter
grounds the model's VALUE, and the application's anchor check parses the printed
ANCHOR it claims to come from. Two spellings of this rule would let the two
halves disagree about the same string -- which is exactly the state that
reported a correctly-read taxable base as contradicted by its own anchor.

**Only a unit this module can name is removed.** A symbol from the closed set
below, or the exact currency code the same document reported. Anything else is
left in place so the decimal authority still refuses it, because "strip
whatever is not a digit" turns a misread into a filing figure. Removing a unit
says nothing about WHICH currency an amount is in: that is the currency field's
own claim, and its validator refuses to guess a code from a symbol.
"""

from __future__ import annotations

__all__ = ["CURRENCY_UNIT_SYMBOLS", "without_currency_unit"]

#: Currency symbols treated as unit markers beside an amount.
CURRENCY_UNIT_SYMBOLS = ("€", "$", "£", "¥")


def without_currency_unit(text: str, currency_unit: str | None = None) -> str:
    """Return *text* with at most ONE leading or trailing currency unit removed.

    Args:
        text: The amount as the document printed it, or as a reader copied it.
        currency_unit: The ISO-4217 code this document reported for itself.
            Required for a code to be recognised as a unit: the ISO authority
            validates SHAPE rather than membership, so accepting any three
            letters would reduce ``1200.00 IVA`` to a figure the document never
            printed under that label. ``None`` recognises only a symbol.

    Returns:
        The text with one unit removed, or unchanged when it carries none this
        rule can name. At most one is removed, so ``1200 EUR EUR`` keeps one
        and still fails the decimal authority.
    """
    stripped = text.strip()
    for symbol in CURRENCY_UNIT_SYMBOLS:
        if stripped.endswith(symbol):
            return stripped[: -len(symbol)].strip()
        if stripped.startswith(symbol):
            return stripped[len(symbol) :].strip()
    if currency_unit is None:
        return stripped
    parts = stripped.split()
    if len(parts) == 2:
        code = currency_unit.strip().upper()
        for index, remainder in ((0, parts[1]), (1, parts[0])):
            if parts[index].strip().upper() == code:
                return remainder.strip()
    return stripped
