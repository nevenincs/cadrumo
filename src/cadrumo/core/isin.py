"""ISO 6166 ISIN shape and check-digit primitives.

One canonical home for validating an International Securities Identification
Number, beside :mod:`core.iban` for the same reason that module exists: every
domain that stores an ISIN needs the same answer, and a second copy drifts.

An ISIN is twelve characters: a two-letter prefix, nine alphanumerics and one
check digit. The check digit is the Luhn digit of the string obtained by
replacing each letter with its two-digit value (A=10 ... Z=35). Modelo 720
(Orden HAP/72/2013 Anexo, type 2 positions 132-143) declares an ISIN under
clave de identificación 1 and requires it "en todo caso" when one is assigned.
"""

from __future__ import annotations

import re

ISIN_SHAPE_RE = re.compile(r"\A[A-Z]{2}[A-Z0-9]{9}[0-9]\Z")
"""ISO 6166 shape: two letters, nine ASCII alphanumerics, one ASCII digit."""


def _expanded_digits(body: str) -> str:
    """Return ``body`` with each letter replaced by its two-digit ISO value."""
    return "".join(str(int(char, 36)) for char in body)


def isin_check_digit(body: str) -> int:
    """Return the ISO 6166 check digit for the first eleven ISIN characters.

    Args:
        body: The eleven-character ISIN without its check digit, uppercase ASCII.

    Returns:
        The single Luhn digit that completes ``body`` into a valid ISIN.
    """
    digits = _expanded_digits(body)
    total = 0
    # Luhn from the right: the digit that will sit next to the check digit is
    # doubled, then every second one moving left.
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 0:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return (10 - total % 10) % 10


def is_valid_isin(value: str) -> bool:
    """Return whether ``value`` is a canonical ISIN with a correct check digit."""
    if not ISIN_SHAPE_RE.match(value):
        return False
    return isin_check_digit(value[:11]) == int(value[11])


__all__ = ["ISIN_SHAPE_RE", "is_valid_isin", "isin_check_digit"]
