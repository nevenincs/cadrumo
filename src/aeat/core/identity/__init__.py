"""Spanish identity-document parsing and validation.

Public surface for NIF / NIE / CIF documents — the identity-number shapes
Spanish taxpayers and legal entities use in tax filings. The module is
intentionally tiny:

* :class:`IdentityDocument` — closed :class:`enum.StrEnum` naming the
  three document kinds.
* :func:`validate_identity` — parses a candidate string and returns the
  matching :class:`IdentityDocument` on success.
* :func:`validate_spanish_tax_id` — pure-string validator that returns
  the canonical form rather than the kind enum, used by call sites that
  only need to check well-formedness.
* :class:`IdentityError` — typed failure shape that registers under the
  stable error code ``INTEGRITY_IDENTITY_DOCUMENT``.
* :data:`SubjectTaxId` — pydantic-ready alias for fields that must carry a
  validated Spanish tax identifier.

The module lives in :mod:`aeat.core` because identity validation is a
domain concern, not a persistence concern. The persistence layer's
redaction rule patterns remain permissive (over-redaction is the safer
failure mode); domain code that needs a strict yes/no answer consumes
this module instead.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator

from ._bucket import BucketId
from ._documents import (
    IdentityDocument,
    IdentityError,
    validate_identity,
)
from ._profile import ProfileId
from ._snapshot import SnapshotId
from ._tax_id import nif_check_letter, validate_spanish_tax_id
from ._transaction import TransactionId


def _subject_tax_id_validator(value: str) -> str:
    """Adapt :func:`validate_spanish_tax_id` for pydantic field validation.

    :class:`IdentityError` extends :class:`ValueError`, so pydantic's
    :class:`~pydantic.AfterValidator` wraps it directly into a
    :class:`~pydantic.ValidationError`. No re-raise shim is needed.
    """
    return validate_spanish_tax_id(value)


type SubjectTaxId = Annotated[str, AfterValidator(_subject_tax_id_validator)]
"""Canonical Spanish NIF / NIE / CIF, validated at the pydantic boundary.

Bare ``str`` fields holding tax identifiers cannot enforce the AEAT
checksum algorithm. Promoting a field to ``SubjectTaxId`` runs
:func:`validate_spanish_tax_id` on assignment and validation, so a
malformed identifier fails fast at the model boundary with an
:class:`IdentityError` rather than leaking into persisted records.
"""

__all__ = [
    "BucketId",
    "IdentityDocument",
    "IdentityError",
    "ProfileId",
    "SnapshotId",
    "SubjectTaxId",
    "TransactionId",
    "nif_check_letter",
    "validate_identity",
    "validate_spanish_tax_id",
]
