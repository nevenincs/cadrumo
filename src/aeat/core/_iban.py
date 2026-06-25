"""Shared ISO 13616 IBAN structural primitives.

One canonical home for the IBAN shape pattern and the mod-97 check residue,
consumed both by the registry casilla boundary (``data_type = "iban"`` via
:mod:`aeat.domain.calculations.registry._schema_scalars`) and by the deadlines
refund-account model (:class:`aeat.domain.deadlines._models.RefundAccount`), so
neither domain package has to import the other to validate an IBAN.
"""

from __future__ import annotations

import re

IBAN_SHAPE_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")
"""ISO 13616 IBAN shape: two-letter country, two check digits, 11-30 BBAN chars."""


def iban_mod_97(canonical: str) -> int:
    """Compute the ISO 13616 IBAN mod-97 check residue for an already-canonical IBAN.

    Move the leading four characters to the tail, replace each letter with its
    ``A=10 … Z=35`` numeric form, and take the resulting integer modulo 97. A
    structurally valid IBAN yields a residue of 1.
    """
    rearranged = canonical[4:] + canonical[:4]
    numeric = "".join(ch if ch.isdigit() else str(ord(ch) - ord("A") + 10) for ch in rearranged)
    return int(numeric) % 97
