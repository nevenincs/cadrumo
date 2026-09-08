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

The bundle version gate is a ceiling with a durability floor: a version
above :data:`BUNDLE_SCHEMA_VERSION` was written by a newer application
and is refused; a version at or above :data:`BUNDLE_DURABILITY_FLOOR` is
readable exactly when the per-hop chain in
:data:`BUNDLE_PAYLOAD_UPGRADERS` reaches the current version. The floor
starts at the current version (no released bundles exist below it) and
only ever moves forward, never back. This module owns schema-version
validation of serialized bundle payloads.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Final

from ...core.errors.hierarchy import CadrumoError
from ...core.storage_taxonomy import StorageCustodyProfile
from ...core.type_adapters import STR_KEYED_MAPPING_ADAPTER

__all__ = [
    "SUPPORTED_BUNDLE_SCHEMA_VERSIONS",
    "UnsupportedBundleSchemaVersionError",
    "serialize_profile_bundle",
    "validate_bundle_payload",
]

if TYPE_CHECKING:
    from ...domain.user_profile.portable_export import UserProfilePortableExport

#: Current bundle write version. Every export stamps this.
BUNDLE_SCHEMA_VERSION: Final[int] = 3

#: Oldest bundle version the import path keeps readable. Starts at the
#: current version (no released bundles exist below it); only ever moves
#: forward, never back.
BUNDLE_DURABILITY_FLOOR: Final[int] = 3

#: One-hop raw-payload upgraders keyed by ``from_version``: each transforms
#: the parsed JSON mapping of a version-N bundle into the version-N+1 shape
#: (including restamping ``bundle_schema_version``) BEFORE strict pydantic
#: validation — the raw mapping is the one sanctioned pre-validation
#: boundary. Empty while the floor equals the current version; a version
#: bump MUST land its hop here in the same change or the lineage gate fails.
BUNDLE_PAYLOAD_UPGRADERS: Mapping[int, Callable[[dict[str, object]], dict[str, object]]] = dict[
    int, Callable[[dict[str, object]], dict[str, object]]
]()

#: Versions the import path accepts: the complete floor-to-current range.
SUPPORTED_BUNDLE_SCHEMA_VERSIONS: frozenset[int] = frozenset(
    range(BUNDLE_DURABILITY_FLOOR, BUNDLE_SCHEMA_VERSION + 1),
)


def _stamped_bundle_version(payload: dict[str, object], *, expected_written_version: int | None) -> int:
    """Read the payload's own stamped schema version, refusing a contradiction.

    A stamped version that disagrees with the one its transport envelope
    declares is refused BEFORE any upgrade runs: the two must agree about
    what shape the bytes are in, or an upgrade hop would be chosen from the
    wrong claim.
    """
    written_version = payload.get("bundle_schema_version")
    if not isinstance(written_version, int) or isinstance(written_version, bool):
        raise UnsupportedBundleSchemaVersionError(
            translated_message="errors.refused.refused_application_registry_input",
            context={
                "written_version": str(written_version),
                "bundle_schema_version_is_integer": False,
            },
        )
    if expected_written_version is not None and written_version != expected_written_version:
        raise UnsupportedBundleSchemaVersionError(
            translated_message="errors.refused.refused_application_registry_input",
            context={
                "written_version": str(written_version),
                "envelope_version": str(expected_written_version),
                "versions_agree": False,
            },
        )
    return written_version


def _refuse_unreadable_bundle_version(written_version: int) -> None:
    """Refuse a version this build cannot read, above the ceiling or below the floor."""
    supported = ",".join(str(version) for version in sorted(SUPPORTED_BUNDLE_SCHEMA_VERSIONS))
    context = {"bundle_schema_version": str(written_version), "supported_versions": supported}
    if written_version > BUNDLE_SCHEMA_VERSION:
        raise UnsupportedBundleSchemaVersionError(
            context=context,
            translated_message="application.user_profile.errors.unsupported_bundle_schema_version",
        )
    if written_version < BUNDLE_DURABILITY_FLOOR:
        raise UnsupportedBundleSchemaVersionError(
            context=context,
            translated_message="application.user_profile.errors.unsupported_bundle_schema_version",
        )


def validate_bundle_payload(
    raw_json: bytes | str,
    *,
    expected_written_version: int | None = None,
) -> UserProfilePortableExport:
    """Parse, chain-upgrade, and strictly validate a serialized bundle payload.

    Reads the payload's own ``bundle_schema_version``, refuses a future
    version (above :data:`BUNDLE_SCHEMA_VERSION`) or one below
    :data:`BUNDLE_DURABILITY_FLOOR`, chain-upgrades an older supported
    payload hop by hop through :data:`BUNDLE_PAYLOAD_UPGRADERS`, and
    validates the result against the current strict
    :class:`~cadrumo.domain.user_profile.portable_export.UserProfilePortableExport` model.

    Args:
        raw_json: The serialized bundle payload (decrypted transport bytes
            or the plaintext export text).
        expected_written_version: When set, the version a transport envelope
            declared for this payload; a payload whose own stamped version
            differs is refused before any upgrade runs.

    Raises:
        UnsupportedBundleSchemaVersionError: When the payload does not carry
            an integer ``bundle_schema_version``, the version is outside the
            floor-to-current range, an upgrade hop is unregistered, or the
            stamped version contradicts ``expected_written_version``.
    """
    from ...domain.user_profile.portable_export import UserProfilePortableExport

    payload = json.loads(raw_json)
    if not isinstance(payload, dict):
        raise UnsupportedBundleSchemaVersionError(
            translated_message="errors.refused.refused_application_registry_input",
            context={"payload_is_json_object": False},
        )
    payload = STR_KEYED_MAPPING_ADAPTER.validate_python(payload)
    written_version = _stamped_bundle_version(payload, expected_written_version=expected_written_version)
    _refuse_unreadable_bundle_version(written_version)
    for hop in range(written_version, BUNDLE_SCHEMA_VERSION):
        upgrader = BUNDLE_PAYLOAD_UPGRADERS.get(hop)
        if upgrader is None:
            raise UnsupportedBundleSchemaVersionError(
                context={
                    "bundle_schema_version": str(written_version),
                    "missing_from_version": str(hop),
                },
                translated_message="application.user_profile.errors.unsupported_bundle_schema_version",
            )
        payload = upgrader(payload)
    # JSON-mode validation: the strict model accepts JSON arrays as tuple
    # fields only on the json path, so the (possibly upgraded) mapping is
    # re-serialized rather than validated as python objects.
    return UserProfilePortableExport.model_validate_json(json.dumps(payload))


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


class UnsupportedBundleSchemaVersionError(CadrumoError):
    """Raised when a bundle carries an unsupported ``bundle_schema_version``."""
