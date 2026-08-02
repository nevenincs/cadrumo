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
* :func:`tax_id_identity_token` and :data:`TaxIdIdentityToken` — the shared
  comparison form for identifiers whose bearer may not be Spanish, used
  wherever a grouping key and a storage key must agree.

The module lives in :mod:`core` because identity validation is a
domain concern, not a persistence concern. The persistence layer's
redaction rule patterns remain permissive (over-redaction is the safer
failure mode); domain code that needs a strict yes/no answer consumes
this module instead.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BeforeValidator

from ._bucket import BucketId
from ._digest import ContentDigest, ContentDigestOrAbsent
from ._documents import (
    IdentityDocument,
    IdentityError,
    validate_identity,
)
from ._nif_iva import (
    NIF_IVA_FORMATS,
    NifIvaFormatSpec,
    NifIvaPrefix,
    nif_iva_format_for_country,
    nif_iva_prefix_for_country,
    normalise_nif_iva,
)
from ._profile import ProfileId
from ._profile_label import ProfileLabel
from ._snapshot import SnapshotId
from ._tax_id import nif_check_letter, tax_id_identity_token, validate_spanish_tax_id
from ._transaction import TransactionId


def _subject_tax_id_validator(value: str) -> str:
    """Adapt :func:`validate_spanish_tax_id` for pydantic field validation.

    :class:`IdentityError` extends :class:`ValueError`, so pydantic's
    :class:`~pydantic.AfterValidator` wraps it directly into a
    :class:`~pydantic.ValidationError`. No re-raise shim is needed.
    """
    return validate_spanish_tax_id(value)


type TaxIdIdentityToken = Annotated[str, BeforeValidator(tax_id_identity_token)]
"""Canonical identity form of a tax identifier, normalised at the boundary.

Runs :func:`tax_id_identity_token` BEFORE the field's own length constraints,
so a field annotated with it stores the canonical token and any ``min_length``
bound is applied to that token rather than to the raw declaration. Unlike
:data:`SubjectTaxId` it asserts no checksum, so it fits identifiers whose
bearer may be non-resident; use :data:`SubjectTaxId` where the value must be a
valid Spanish NIF / NIE / CIF.
"""

type SubjectTaxId = Annotated[str, AfterValidator(_subject_tax_id_validator)]
"""Canonical Spanish NIF / NIE / CIF, validated at the pydantic boundary.

Bare ``str`` fields holding tax identifiers cannot enforce the AEAT
checksum algorithm. Promoting a field to ``SubjectTaxId`` runs
:func:`validate_spanish_tax_id` on assignment and validation, so a
malformed identifier fails fast at the model boundary with an
:class:`IdentityError` rather than leaking into persisted records.
"""

__all__ = [
    "NIF_IVA_FORMATS",
    "BucketId",
    "ContentDigest",
    "ContentDigestOrAbsent",
    "IdentityDocument",
    "IdentityError",
    "NifIvaFormatSpec",
    "NifIvaPrefix",
    "ProfileId",
    "ProfileLabel",
    "SnapshotId",
    "SubjectTaxId",
    "TaxIdIdentityToken",
    "TransactionId",
    "nif_check_letter",
    "nif_iva_format_for_country",
    "nif_iva_prefix_for_country",
    "normalise_nif_iva",
    "tax_id_identity_token",
    "validate_identity",
    "validate_spanish_tax_id",
]
