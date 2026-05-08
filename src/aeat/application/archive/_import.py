"""Restore an :class:`ArchiveBundle` into the encrypted SQL backend."""

from __future__ import annotations

import base64
import json

from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.logging import get_logger
from ._errors import ArchiveBundleSchemaError, ArchiveConflictError
from ._models import (
    ARCHIVE_BUNDLE_SCHEMA_VERSION,
    ArchiveBundle,
    ArchiveRecord,
    ConflictPolicy,
    RestoreEntry,
    RestoreOutcome,
    RestoreReport,
)
from ._registry import KeyStrategy, archive_adapter_for

_log = get_logger(__name__)


def _record_label(record: ArchiveRecord) -> str:
    """Return the payload-keyed natural key, or ``hashed:<digest>`` otherwise."""
    if record.object_key is not None:
        return record.object_key
    return f"hashed:{record.hashed_object_key_b64}"


def _record_exists(repo: SecureObjectRepository, record: ArchiveRecord) -> bool:
    """Return ``True`` if ``record`` collides with an existing row."""
    if record.object_key is not None:
        return repo.exists(record.namespace, record.object_key)
    digest = base64.b64decode((record.hashed_object_key_b64 or "").encode("ascii"), validate=True)
    return repo.exists_by_raw_key(record.namespace, digest)


def restore_archive(
    bundle: ArchiveBundle,
    *,
    conflict_policy: ConflictPolicy = ConflictPolicy.FAIL,
    repository: SecureObjectRepository | None = None,
) -> RestoreReport:
    """Write every :class:`ArchiveRecord` in ``bundle`` back into the backend.

    Each record is re-encoded as a fresh JSON envelope (the bundle
    stores the parsed JSON dict, not the byte payload) and re-saved
    through :class:`SecureObjectRepository`. Payload-keyed records use
    the natural ``object_key``; hashed-passthrough records route
    through :meth:`SecureObjectRepository.save_with_raw_key` and the
    raw HMAC digest captured at export time.

    Args:
        bundle: The bundle to restore.
        conflict_policy: How to handle records whose key already
            exists in the backend. Defaults to
            :attr:`ConflictPolicy.FAIL` so collisions abort the
            operation rather than silently overwriting financial data.
        repository: Optional override of the storage backend; defaults
            to a fresh :class:`SecureObjectRepository`.

    Raises:
        :exc:`ArchiveBundleSchemaError`: If the bundle's wire schema
            version is newer than this consumer supports.
        :exc:`ArchiveAdapterMissingError`: If a record's namespace has
            no registered adapter.
        :exc:`ArchiveConflictError`: If ``conflict_policy`` is
            :attr:`ConflictPolicy.FAIL` and a collision is encountered;
            no records have been written when this is raised.

    Returns:
        A :class:`RestoreReport` listing the per-record outcome.
    """
    if bundle.bundle_schema_version > ARCHIVE_BUNDLE_SCHEMA_VERSION:
        raise ArchiveBundleSchemaError(
            f"archive bundle schema version {bundle.bundle_schema_version} exceeds "
            f"consumer-supported {ARCHIVE_BUNDLE_SCHEMA_VERSION}",
        )

    repo = repository or SecureObjectRepository()

    if conflict_policy is ConflictPolicy.FAIL:
        for record in bundle.records:
            if _record_exists(repo, record):
                raise ArchiveConflictError(
                    f"archive restore would overwrite {record.namespace}/{_record_label(record)}; "
                    f"re-run with conflict_policy={ConflictPolicy.OVERWRITE.value!r} or "
                    f"{ConflictPolicy.KEEP.value!r}",
                )

    entries: list[RestoreEntry] = []
    for record in bundle.records:
        adapter = archive_adapter_for(record.namespace)
        existed = _record_exists(repo, record)
        label = _record_label(record)
        if existed and conflict_policy is ConflictPolicy.KEEP:
            entries.append(
                RestoreEntry(
                    namespace=record.namespace,
                    object_key=label,
                    outcome=RestoreOutcome.SKIPPED_KEEP,
                )
            )
            continue
        payload_bytes = json.dumps(record.envelope_json).encode("utf-8")
        if adapter.key_strategy is KeyStrategy.HASHED_PASSTHROUGH:
            digest = base64.b64decode((record.hashed_object_key_b64 or "").encode("ascii"), validate=True)
            repo.save_with_raw_key(
                namespace=record.namespace,
                hashed_object_key=digest,
                classification=adapter.classification,
                schema_version=record.schema_version,
                written_at=record.written_at,
                payload=payload_bytes,
            )
        else:
            assert record.object_key is not None  # validated by ArchiveRecord
            repo.save(
                namespace=record.namespace,
                object_key=record.object_key,
                classification=adapter.classification,
                schema_version=record.schema_version,
                written_at=record.written_at,
                payload=payload_bytes,
            )
        entries.append(
            RestoreEntry(
                namespace=record.namespace,
                object_key=label,
                outcome=RestoreOutcome.OVERWROTE if existed else RestoreOutcome.WROTE,
            )
        )
    _log.info(
        "archive restore: applied bundle %s -- %d record(s) processed",
        bundle.bundle_id,
        len(entries),
    )
    return RestoreReport(bundle_id=bundle.bundle_id, entries=tuple(entries))


__all__ = ["restore_archive"]
