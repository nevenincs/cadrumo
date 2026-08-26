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
* :func:`same_tax_identifier` — the shared "these name the same bearer"
  predicate, checksum-free and separator-insensitive, for the places that
  compare an identifier rather than key on it.
* :data:`AeatExpedienteId`, :data:`AeatClaveLiquidacion`,
  :data:`AeatPresentationId`, and the sibling AEAT document-identifier
  aliases — their source-specific constraints remain declared once and are
  imported through this facade by every consumer.

The module lives in :mod:`core` because identity validation is a
domain concern, not a persistence concern. The persistence layer's
redaction rule patterns remain permissive (over-redaction is the safer
failure mode); domain code that needs a strict yes/no answer consumes
this module instead.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, Field

from .._hex import Hex64Str as _Hex64Str
from ._bucket import BucketId, canonical_bucket_id
from ._digest import ContentDigest, ContentDigestOrAbsent, PrefixedContentDigest
from ._documents import (
    IdentityDocument,
    IdentityError,
    validate_identity,
)
from ._namespace import (
    AEAT_EXPEDIENTE_ID_MAX_LENGTH,
    AEAT_EXPEDIENTE_ID_MIN_LENGTH,
    AEAT_EXPEDIENTE_ID_PATTERN,
    AeatBoxNumber,
    AeatCertificadoId,
    AeatClaveLiquidacion,
    AeatCsv,
    AeatExpedienteId,
    AeatPresentationId,
    RegistrySnapshotId,
)
from ._nif_iva import (
    NIF_IVA_FORMATS,
    NifIvaFormatSpec,
    NifIvaPrefix,
    iso_country_for_nif_iva_prefix,
    nif_iva_format_for_country,
    nif_iva_prefix_for_country,
    normalise_nif_iva,
)
from ._profile import ProfileId, canonical_profile_bucket_id
from ._profile_label import ProfileLabel
from ._tax_id import (
    SPANISH_TAX_ID_WIDTH,
    nif_check_letter,
    same_tax_identifier,
    tax_id_identity_token,
    validate_spanish_tax_id,
)

SnapshotId = _Hex64Str
"""Hex-64 content-addressed snapshot identity.

A snapshot identity is the SHA-256 hex digest of the canonical JSON form of
the underlying snapshot payload. Two equal snapshots serialise to identical
ids, so consumers can deduplicate captures cheaply and verify content
addressing offline without contacting AEAT. Declared here directly (rather
than as a bridge module) because it adds no constraint beyond
:data:`Hex64Str` itself.

Surfaces that mint a snapshot id with a non-hex shape (notably the censo
snapshot, which derives its id from a JSON-canonical ``content_hash_hex``
family) do not consume this alias; they are referential identities outside
the content-addressed-hex family.
"""

WorkUnitId = _Hex64Str
"""Hex-64 identity of one modelo work unit.

The work unit is the addressable subject of the modelo workflow, so its
identity is named by nearly every layer above the record: the workflow engine,
the modelo application services, the persistence adapters and the CLI payload
surface. Declared here because it adds no constraint beyond :data:`Hex64Str`,
which is the discipline every hex-64 identity concept in this codebase follows.
"""

CalculationRevisionId = _Hex64Str
"""Hex-64 identity of one calculation revision under a work unit.

Declared here rather than in the modelo domain because the identity is
consumed across package boundaries -- the modelo application surface and three
CLI payload modules each name one -- and because it adds no constraint beyond
:data:`Hex64Str`, which is the discipline every hex-64 identity concept in
this codebase follows.
"""

FilingRecordId = _Hex64Str
"""Hex-64 identity of one filing record bound to a calculation revision.

Declared here rather than in the modelo domain because the identity is
consumed across package boundaries -- the evidence and cross-period
application surfaces and the CLI payload layer each name one -- and because it
adds no constraint beyond :data:`Hex64Str`, which is the discipline every
hex-64 identity concept in this codebase follows.
"""

VerificationReportId = _Hex64Str
"""Hex-64 identity of one verification report bound to a calculation revision.

Declared here rather than in the modelo domain because the identity is consumed
across package boundaries — the CLI payload surface holds one — and because it
adds no constraint beyond :data:`Hex64Str`, which is the discipline every
hex-64 identity concept in this codebase follows.
"""

InvoiceId = _Hex64Str
"""Hex-64 content-addressed invoice identity.

Minted by the invoice domain when an invoice is persisted. Declared here
rather than in that domain because the identity is consumed across package
boundaries — the ledger application surface and the CLI payload layer both
hold one — and because it adds no constraint beyond :data:`Hex64Str`, which
is the discipline every hex-64 identity concept in this codebase follows.
"""

TransactionId = _Hex64Str
"""Hex-64 content-addressed ledger-transaction identity.

Minted by the transaction domain when a ledger entry is persisted. Declared
here directly (rather than as a bridge module) because it adds no
constraint beyond :data:`Hex64Str` itself; the constraint shape is consumed
by sibling domains (notably :mod:`domain.invoices` for reconciliation
models), the application ledger service, and the persistence adapters.
"""

ModeloEditBaselineId = _Hex64Str
"""Hex-64 opaque identity of one admitted Modelo edit compare-and-swap baseline.

Declared here rather than in the modelo application package because it adds
no constraint beyond :data:`Hex64Str`, which is the discipline every hex-64
identity concept in this codebase follows; the persistence adapter and any
future cross-package consumer resolve the same canonical identity.
"""

ModeloEditMutationResultReceiptId = _Hex64Str
"""Hex-64 content-addressed identity of one Modelo edit mutation result receipt.

Minted when a guarded edit compare-and-swap commits. Declared here rather than
in the modelo application package because it adds no constraint beyond
:data:`Hex64Str`, which is the discipline every hex-64 identity concept in
this codebase follows, and because the encrypted receipt repository resolves
the same canonical identity as the application execution service.
"""

ContinuidadId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9_-]*[a-z0-9]$|^[a-z0-9]$",
    ),
]
"""Stable cross-revision casilla-continuity identity.

Continuity chains are consumed by the registry schema and application read
models, while their segment-safe constraint is independent from either
producer. The shared identity home prevents a registry facade bridge from
becoming a second public owner.
"""


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
    "AEAT_EXPEDIENTE_ID_MAX_LENGTH",
    "AEAT_EXPEDIENTE_ID_MIN_LENGTH",
    "AEAT_EXPEDIENTE_ID_PATTERN",
    "NIF_IVA_FORMATS",
    "SPANISH_TAX_ID_WIDTH",
    "AeatBoxNumber",
    "AeatCertificadoId",
    "AeatClaveLiquidacion",
    "AeatCsv",
    "AeatExpedienteId",
    "AeatPresentationId",
    "BucketId",
    "CalculationRevisionId",
    "ContentDigest",
    "ContentDigestOrAbsent",
    "ContinuidadId",
    "FilingRecordId",
    "IdentityDocument",
    "IdentityError",
    "InvoiceId",
    "ModeloEditBaselineId",
    "ModeloEditMutationResultReceiptId",
    "NifIvaFormatSpec",
    "NifIvaPrefix",
    "PrefixedContentDigest",
    "ProfileId",
    "ProfileLabel",
    "RegistrySnapshotId",
    "SnapshotId",
    "SubjectTaxId",
    "TaxIdIdentityToken",
    "TransactionId",
    "VerificationReportId",
    "WorkUnitId",
    "canonical_bucket_id",
    "canonical_profile_bucket_id",
    "iso_country_for_nif_iva_prefix",
    "nif_check_letter",
    "nif_iva_format_for_country",
    "nif_iva_prefix_for_country",
    "normalise_nif_iva",
    "same_tax_identifier",
    "tax_id_identity_token",
    "validate_identity",
    "validate_spanish_tax_id",
]
