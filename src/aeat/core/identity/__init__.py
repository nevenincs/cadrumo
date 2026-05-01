"""Spanish identity-document parsing + validation.

Public surface for NIF / NIE / CIF documents — the three identity-
number shapes Spanish autónomos, individuals, and legal entities use
in tax filings. The module is intentionally tiny:

- :class:`IdentityDocument` is the closed StrEnum naming the three
  document kinds.
- :func:`validate_identity` parses a candidate string and returns
  the matching :class:`IdentityDocument` on success.
- :class:`IdentityError` is the typed failure shape; it registers
  a stable :class:`ErrorCode` (``INTEGRITY_IDENTITY_DOCUMENT``).

The module lives outside :mod:`aeat.adapters.persistence.storage` because identity
validation is a domain concern, not a persistence concern. The
substrate's redaction rule patterns remain permissive (over-
redaction is the safer failure mode); domain code that needs a
strict yes / no consumes this module instead.
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
