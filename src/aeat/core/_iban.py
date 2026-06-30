"""Shared ISO 13616 IBAN shape and checksum primitives.

One canonical home for the :data:`IBAN_SHAPE_RE` pattern and
:func:`iban_mod_97` check residue, consumed by
:data:`aeat.domain.calculations.registry._schema.IbanString` for registry
casillas declaring ``data_type = "iban"`` and by the secure-storage
:class:`~aeat.domain.deadlines.RefundAccount` model. Keeping the primitives in
``core`` lets each domain validate an IBAN without importing the other.

This module does not canonicalise operator input, decide whether a blank IBAN is
allowed, or choose the public error type. Registry casilla validation rejects
blank IBAN data, while the refund-account model treats ``None`` and blank input
as "no account on file"; both call these primitives after applying their own
boundary policy.
"""

from __future__ import annotations

import re

IBAN_SHAPE_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")
"""ISO 13616 IBAN shape shared by registry and refund-account validators.

The pattern checks uppercase canonical text only: country code, two check
digits, and an alphanumeric BBAN for a total length of 15-34 characters. It is
only the structural gate; callers must also run :func:`iban_mod_97`.
"""


def iban_mod_97(canonical: str) -> int:
    """Compute the ISO 13616 IBAN mod-97 check residue for an already-canonical IBAN.

    Callers normalize separators and case before matching
    :data:`IBAN_SHAPE_RE`; see
    :func:`aeat.domain.calculations.registry._schema._validate_iban_string` and
    :meth:`aeat.domain.deadlines.RefundAccount._validate_iban`. This helper
    moves the leading four characters to the tail, replaces each letter with its
    ``A=10 ... Z=35`` numeric form, and returns the integer modulo 97. A valid
    IBAN yields a residue of 1.

    Args:
        canonical: Uppercase, separator-free IBAN text that has already matched
            :data:`IBAN_SHAPE_RE`.

    Returns:
        The ISO 13616 check residue. ``1`` means the check digits are valid.
    """
    rearranged = canonical[4:] + canonical[:4]
    numeric = "".join(ch if ch.isdigit() else str(ord(ch) - ord("A") + 10) for ch in rearranged)
    return int(numeric) % 97
