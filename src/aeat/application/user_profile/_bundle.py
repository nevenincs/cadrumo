"""Bundled-export serialiser and deserialiser for :class:`UserProfilePortableExport`.

The serialiser reads all four financial-history categories from the
active bucket's repositories and populates the v2 bundle fields.
The :class:`TransactionCatalogue` is loaded via
:class:`TransactionCatalogueRepository` and is one of the four payload
categories included in each export bundle.

S106 — deserialiser: validates ``bundle_schema_version`` against
``SUPPORTED_BUNDLE_SCHEMA_VERSIONS`` before parsing; imports work units,
ledger transactions, calculation revisions, and filing records via their
respective repository save paths.

ADR decisions honoured here:

  D2 — no encrypted-material blobs; decrypted domain-model payloads only.
  D3 — ``model_dump(mode="json")`` / ``model_validate()`` throughout; no
  ``dict[str, Any]`` intermediate; ``exclude_none=True`` forbidden.
  D4 — version constant validated at import boundary; unsupported versions
  raise ``CliRefusedBoundaryError``.
  D5 — bundle ``profile_id`` is preserved; two-tier collision guard runs
  before any write.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.errors import AeatError

if TYPE_CHECKING:
    from ...domain.user_profile._portable_export import UserProfilePortableExport


#: Versions the import path will accept.  Add new integers here when
#: a new schema version is introduced; never remove existing ones.
SUPPORTED_BUNDLE_SCHEMA_VERSIONS: frozenset[int] = frozenset({1, 2})


# ---------------------------------------------------------------------------
# Serialiser — S105
# ---------------------------------------------------------------------------


def serialize_profile_bundle(*, bucket_id: str) -> UserProfilePortableExport:
    """Build a v2 portable export bundle for ``bucket_id``.

    Reads the profile record and all four financial-history categories
    from the bucket's encrypted repositories and assembles them into a
    :class:`UserProfilePortableExport`.  The caller is responsible for
    ensuring a live :class:`BucketSession` is active for ``bucket_id``.

    The bundle carries only decrypted pydantic domain-model payloads
    (ADR D2).  The recipient re-encrypts each object under their own
    bucket DEK via the standard repository save path on import.
    """
    from ...domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
    from ...domain.modelos._filing_repository import ModeloRecordCatalogueRepository
    from ...domain.modelos._repository import WorkUnitCatalogueRepository
    from ...domain.transactions._repository import TransactionCatalogueRepository
    from ...domain.user_profile._portable_export import UserProfilePortableExport
    from ._orchestration import build_lifecycle_service

    record = build_lifecycle_service(bucket_id=bucket_id).read(bucket_id)

    work_unit_catalogue = WorkUnitCatalogueRepository(bucket_id=bucket_id).load()
    work_units = tuple(work_unit_catalogue)

    transaction_catalogue = TransactionCatalogueRepository(bucket_id=bucket_id).load()
    ledger_transactions = tuple(transaction_catalogue)

    revision_catalogue = CalculationRevisionCatalogueRepository(bucket_id=bucket_id).load()
    calculation_revisions = tuple(revision_catalogue)

    filing_catalogue = ModeloRecordCatalogueRepository(bucket_id=bucket_id).load()
    filing_records = tuple(filing_catalogue)

    return UserProfilePortableExport(
        bundle_schema_version=2,
        profile=record,
        work_units=work_units,
        ledger_transactions=ledger_transactions,
        calculation_revisions=calculation_revisions,
        filing_records=filing_records,
    )


# ---------------------------------------------------------------------------
# Deserialiser — S106
# ---------------------------------------------------------------------------


def deserialize_profile_bundle(bundle: UserProfilePortableExport, *, target_bucket_id: str) -> None:
    """Import financial-history objects from ``bundle`` into ``target_bucket_id``.

    Validates ``bundle.bundle_schema_version`` against
    ``SUPPORTED_BUNDLE_SCHEMA_VERSIONS`` before any writes (ADR D4).

    For v1 bundles: no financial-history objects to import — the caller
    handles profile-record provisioning via the atomic-create path.

    For v2 bundles: saves work units, ledger transactions, calculation
    revisions, and filing records into the target bucket via the standard
    repository save paths.  Each domain object is re-encrypted under the
    target bucket's own DEK (ADR D2).  No ``dict[str, Any]`` intermediate
    is used; pydantic models flow directly into typed catalogue saves (ADR D3).

    The caller is responsible for:
      - Provisioning the target bucket before calling this function.
      - Ensuring a live :class:`BucketSession` is active for ``target_bucket_id``.
      - Running the two-tier collision guard (ADR D5) before provisioning.

    Args:
        bundle: The validated export bundle.
        target_bucket_id: The bucket id under which to write the objects.

    Raises:
        UnsupportedBundleSchemaVersionError: When
            ``bundle.bundle_schema_version`` is not in
            ``SUPPORTED_BUNDLE_SCHEMA_VERSIONS``.
    """
    if bundle.bundle_schema_version not in SUPPORTED_BUNDLE_SCHEMA_VERSIONS:
        raise UnsupportedBundleSchemaVersionError(
            f"bundle_schema_version {bundle.bundle_schema_version!r} is not supported; "
            f"supported versions: {sorted(SUPPORTED_BUNDLE_SCHEMA_VERSIONS)}"
        )

    if bundle.bundle_schema_version == 1:
        # v1 is facts-only; no financial-history objects to write.
        return

    # v2: import all four financial-history categories.
    _import_work_units(bundle, target_bucket_id=target_bucket_id)
    _import_ledger_transactions(bundle, target_bucket_id=target_bucket_id)
    _import_calculation_revisions(bundle, target_bucket_id=target_bucket_id)
    _import_filing_records(bundle, target_bucket_id=target_bucket_id)


def _import_work_units(bundle: UserProfilePortableExport, *, target_bucket_id: str) -> None:
    from ...domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit

    if not bundle.work_units:
        return
    repo = WorkUnitCatalogueRepository(bucket_id=target_bucket_id)
    catalogue = repo.load()
    for unit in bundle.work_units:
        catalogue = upsert_work_unit(catalogue, unit)
    repo.save(catalogue)


def _import_ledger_transactions(bundle: UserProfilePortableExport, *, target_bucket_id: str) -> None:
    from ...domain.transactions._models import Transaction, TransactionCatalogue
    from ...domain.transactions._repository import TransactionCatalogueRepository

    if not bundle.ledger_transactions:
        return
    repo = TransactionCatalogueRepository(bucket_id=target_bucket_id)
    existing = repo.load()
    merged: dict[str, Transaction] = dict(existing.transactions)
    for txn in bundle.ledger_transactions:
        merged[txn.transaction_id] = txn
    repo.save(TransactionCatalogue(transactions=merged))


def _import_calculation_revisions(bundle: UserProfilePortableExport, *, target_bucket_id: str) -> None:
    from ...domain.modelos._calculation_repository import (
        CalculationRevisionCatalogueRepository,
        upsert_calculation_revision,
    )

    if not bundle.calculation_revisions:
        return
    repo = CalculationRevisionCatalogueRepository(bucket_id=target_bucket_id)
    catalogue = repo.load()
    for revision in bundle.calculation_revisions:
        catalogue = upsert_calculation_revision(catalogue, revision)
    repo.save(catalogue)


def _import_filing_records(bundle: UserProfilePortableExport, *, target_bucket_id: str) -> None:
    from ...domain.modelos._filing_repository import ModeloRecordCatalogueRepository, upsert_filing_record

    if not bundle.filing_records:
        return
    repo = ModeloRecordCatalogueRepository(bucket_id=target_bucket_id)
    catalogue = repo.load()
    for record in bundle.filing_records:
        catalogue = upsert_filing_record(catalogue, record)
    repo.save(catalogue)


class UnsupportedBundleSchemaVersionError(AeatError):
    """Raised when a bundle carries an unsupported ``bundle_schema_version``."""
