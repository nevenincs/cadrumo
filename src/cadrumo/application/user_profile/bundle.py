"""Portable profile-bundle serialisation and payload validation.

This module composes
:class:`~cadrumo.domain.user_profile.portable_export.UserProfilePortableExport` payloads at
the application boundary. A v3 bundle contains the profile record plus
the four bucket-local history categories that must move with it: work
units, ledger transactions, calculation revisions, and filing records.
The v3 shape additionally carries the generic secure-object custody
schema and coverage manifest, default-empty until the transport-aware
phases populate them.
The ledger category is loaded as a
:class:`~cadrumo.domain.transactions.TransactionCatalogue` through its
application-owned repository port.

Bundles carry typed domain-model payloads, not encrypted blobs, key
material, or raw secure-storage rows. Export reads domain records from
their owning repositories.

The serializer stamps the current bundle version on every exported payload.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ...core.storage_taxonomy import StorageCustodyProfile

__all__ = [
    "serialize_profile_bundle",
]

if TYPE_CHECKING:
    from ...domain.user_profile.portable_export import UserProfilePortableExport

#: Current bundle write version. Every export stamps this.
BUNDLE_SCHEMA_VERSION: Final[int] = 3

# ---------------------------------------------------------------------------
# Serialiser
# ---------------------------------------------------------------------------


def serialize_profile_bundle(
    *,
    bucket_id: str,
    custody_profile: StorageCustodyProfile | str = StorageCustodyProfile.STRUCTURED,
) -> UserProfilePortableExport:
    """Build a v3 :class:`~cadrumo.domain.user_profile.portable_export.UserProfilePortableExport`.

    Reads the profile record and all four financial-history categories
    from ``bucket_id``'s encrypted repositories and assembles them into
    one portable payload. The caller is responsible for ensuring a live
    bucket session is active for ``bucket_id``.

    Args:
        bucket_id: Profile bucket whose domain repositories are exported.
        custody_profile: Secure-object custody scope to apply, as a
            :class:`~cadrumo.core.StorageCustodyProfile`
            or one of its string values.

    The bundle carries only decrypted pydantic domain-model payloads
    (no encrypted envelopes or key material). The recipient re-encrypts
    each object under its own bucket data-encryption key through the
    standard repository save paths on import.
    """
    from ...domain.user_profile.portable_export import UserProfilePortableExport
    from ..ledger.transaction_repository import transaction_catalogue_repository
    from ..modelo.calculation_repository import calculation_revision_catalogue_repository
    from ..modelo.filing_repository import modelo_record_catalogue_repository
    from ..modelo.work_unit_repository import work_unit_catalogue_repository
    from .custody_carry import build_secure_object_custody_payload, normalize_storage_custody_profile
    from .profile_record_repository import ProfileRecordRepository

    record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)

    work_unit_catalogue = work_unit_catalogue_repository(bucket_id=bucket_id).load()
    work_units = tuple(work_unit_catalogue)

    transaction_catalogue = transaction_catalogue_repository(bucket_id=bucket_id).load()
    ledger_transactions = tuple(transaction_catalogue)

    revision_catalogue = calculation_revision_catalogue_repository(bucket_id=bucket_id).load()
    calculation_revisions = tuple(revision_catalogue)

    filing_catalogue = modelo_record_catalogue_repository(bucket_id=bucket_id).load()
    filing_records = tuple(filing_catalogue)

    carried_objects, coverage_manifest = build_secure_object_custody_payload(
        bucket_id=bucket_id,
        custody_profile=normalize_storage_custody_profile(custody_profile),
    )

    return UserProfilePortableExport(
        bundle_schema_version=BUNDLE_SCHEMA_VERSION,
        profile=record,
        work_units=work_units,
        ledger_transactions=ledger_transactions,
        calculation_revisions=calculation_revisions,
        filing_records=filing_records,
        carried_objects=carried_objects,
        coverage_manifest=coverage_manifest,
    )
