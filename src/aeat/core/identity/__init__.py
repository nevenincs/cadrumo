"""Spanish identity-document parsing and validation.

Public surface for NIF / NIE / CIF documents — the three identity-number
shapes Spanish autónomos, individuals, and legal entities use in tax
filings. The module is intentionally tiny:

* :class:`IdentityDocument` — closed :class:`enum.StrEnum` naming the
  three document kinds.
* :func:`validate_identity` — parses a candidate string and returns the
  matching :class:`IdentityDocument` on success.
* :func:`validate_spanish_tax_id` — pure-string validator that returns
  the canonical form rather than the kind enum, used by call sites that
  only need to check well-formedness.
* :class:`IdentityError` — typed failure shape that registers under the
  stable error code ``INTEGRITY_IDENTITY_DOCUMENT``.

The module lives in :mod:`aeat.core` because identity validation is a
domain concern, not a persistence concern. The persistence layer's
redaction rule patterns remain permissive (over-redaction is the safer
failure mode); domain code that needs a strict yes/no answer consumes
this module instead.
"""

from __future__ import annotations

from ._documents import (
    IdentityDocument,
    IdentityError,
    validate_identity,
)
from ._tax_id import validate_spanish_tax_id

__all__ = [
    "IdentityDocument",
    "IdentityError",
    "validate_identity",
    "validate_spanish_tax_id",
]
