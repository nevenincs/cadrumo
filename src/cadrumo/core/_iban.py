"""Shared ISO 13616 IBAN shape and checksum primitives.

One canonical home for the :data:`IBAN_SHAPE_RE` pattern and
:func:`iban_mod_97` check residue, consumed by
:data:`domain.calculations.registry._schema.IbanString` for registry
casillas declaring ``data_type = "iban"`` and by the secure-storage
:class:`~domain.deadlines.RefundAccount` model. Keeping the primitives in
``core`` lets each domain validate an IBAN without importing the other.

Canonicalising the printed form is :func:`normalise_iban`, which lives here
beside the shape and the checksum because every consumer needs the same answer
before it can ask either of them: an IBAN is printed in groups of four on a bank
statement and an invoice footer, so the separator-free spelling the shape gate
accepts is the one that does NOT arrive. Two validators open-coded the same
three-call canonicalisation and a third consumer -- the confidentiality funnel
-- had no canonicalisation at all, which is what made the grouped rendering
readable in operator output.

This module still does not decide whether a blank IBAN is allowed or choose the
public error type. Registry casilla validation rejects blank IBAN data, while
the refund-account model treats ``None`` and blank input as "no account on
file"; both call these primitives after applying their own boundary policy.
"""

from __future__ import annotations

import re

IBAN_SHAPE_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")
"""ISO 13616 IBAN shape shared by registry and refund-account validators.

The pattern checks uppercase canonical text only: country code, two check
digits, and an alphanumeric BBAN for a total length of 15-34 characters. It is
only the structural gate; callers must also run :func:`iban_mod_97`.
"""


def normalise_iban(value: str) -> str:
    """Return the uppercase, separator-free form of a printed IBAN.

    An IBAN is essentially always printed in groups of four -- that is how it
    leaves a bank statement, an invoice footer and an operator's clipboard --
    and hyphenated renderings are common too. :data:`IBAN_SHAPE_RE` matches only
    the canonical spelling, so every consumer must fold the printed form onto it
    before asking the shape or :func:`iban_mod_97` anything.

    Args:
        value: An IBAN as printed, with or without separators.

    Returns:
        The uppercased value with spaces and hyphens removed. The result is not
        asserted to be a valid IBAN; the caller still runs the shape gate and
        the checksum.
    """
    return value.replace(" ", "").replace("-", "").upper()


def iban_mod_97(canonical: str) -> int:
    """Compute the ISO 13616 IBAN mod-97 check residue for an already-canonical IBAN.

    Existing callers normalize separators and case and independently re-check
    :data:`IBAN_SHAPE_RE` before calling this; see
    :func:`domain.calculations.registry._schema._validate_iban_string` and
    :meth:`domain.deadlines.RefundAccount._validate_iban`. Those call-site
    gates are harmless belt-and-braces now that the shape is enforced here
    too, but they must not be the ONLY thing standing between a malformed
    string and a "valid" answer: a caller that forgets its own gate must
    still be refused, not silently pass. ``iban_mod_97("ES82")`` -- four
    characters, no BBAN at all -- previously returned ``1`` (a false
    "valid"), because the mod-97 arithmetic tolerates any string long enough
    to slice; nothing in the function itself demanded a real IBAN shape.

    This helper moves the leading four characters to the tail, replaces each
    letter with its ``A=10 ... Z=35`` numeric form, and returns the integer
    modulo 97. A valid IBAN yields a residue of 1.

    Args:
        canonical: Uppercase, separator-free IBAN text.

    Returns:
        The ISO 13616 check residue. ``1`` means the check digits are valid.

    Raises:
        ValueError: If ``canonical`` does not match :data:`IBAN_SHAPE_RE` --
            it cannot be a real IBAN, so no residue is computed at all rather
            than an arithmetically well-formed but meaningless one.
    """
    if not IBAN_SHAPE_RE.match(canonical):
        raise ValueError(f"iban_mod_97 requires an ISO 13616-shaped IBAN, got {canonical!r}")
    rearranged = canonical[4:] + canonical[:4]
    numeric = "".join(ch if ch.isdigit() else str(ord(ch) - ord("A") + 10) for ch in rearranged)
    return int(numeric) % 97
