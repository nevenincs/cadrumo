"""Walk every registered namespace and produce an :class:`ArchiveBundle`."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime

from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.logging import get_logger
from ._errors import ArchiveAdapterMissingError, ArchiveBundleSchemaError
from ._models import ARCHIVE_BUNDLE_SCHEMA_VERSION, ArchiveBundle, ArchiveRecord
from ._registry import KeyStrategy, all_archive_adapters, archive_adapter_for

_log = get_logger(__name__)


def create_archive(
    *,
    namespaces: tuple[str, ...] | None = None,
    bundle_id: str | None = None,
    repository: SecureObjectRepository | None = None,
) -> ArchiveBundle:
    """Produce an :class:`ArchiveBundle` covering registered namespaces.

    Args:
        namespaces: Optional explicit subset to export. ``None`` exports
            every registered namespace, ordered by namespace string.
            Each entry must be a registered namespace; unknown entries
            raise :class:`aeat.application.archive.ArchiveAdapterMissingError`.
        bundle_id: Optional caller-supplied bundle identifier; defaults
            to a fresh UUID4 hex string.
        repository: Optional override of the storage backend used by
            the export walker; defaults to a fresh
            :class:`SecureObjectRepository` bound to the active engine.

    Returns:
        The populated :class:`ArchiveBundle`. Records are emitted in
        ``(namespace, object_key)`` order for stable diffability.
    """
    repo = repository or SecureObjectRepository()
    adapters = (
        all_archive_adapters()
        if namespaces is None
        else tuple(archive_adapter_for(namespace) for namespace in namespaces)
    )
    records: list[ArchiveRecord] = []
    for adapter in adapters:
        for stored in repo.list_records(
            adapter.namespace,
            expected_class=adapter.classification,
            max_supported_version=adapter.schema_version,
        ):
            envelope_json = json.loads(stored.payload.decode("utf-8"))
            payload = envelope_json.get("payload")
            if not isinstance(payload, dict):
                raise ArchiveBundleSchemaError(
                    f"archive export: namespace {adapter.namespace!r} envelope payload is not a JSON object",
                )
            # SQLite drops tzinfo at the column boundary even with
            # ``DateTime(timezone=True)`` declared; rows saved as UTC
            # come back naive. Re-attach UTC so the bundle's
            # tz-aware contract holds.
            written_at = stored.written_at
            if written_at.tzinfo is None or written_at.utcoffset() is None:
                written_at = written_at.replace(tzinfo=UTC)
            if adapter.key_strategy is KeyStrategy.HASHED_PASSTHROUGH:
                records.append(
                    ArchiveRecord(
                        namespace=adapter.namespace,
                        object_key=None,
                        hashed_object_key_b64=base64.b64encode(stored.object_key).decode("ascii"),
                        classification=adapter.classification,
                        schema_version=stored.schema_version,
                        written_at=written_at,
                        envelope_json=envelope_json,
                    )
                )
                continue
            if adapter.extract_object_key is None:
                raise ArchiveAdapterMissingError(
                    f"adapter for {adapter.namespace!r} declares PAYLOAD_FIELD strategy "
                    f"but provides no extract_object_key callable",
                )
            object_key = adapter.extract_object_key(payload)
            records.append(
                ArchiveRecord(
                    namespace=adapter.namespace,
                    object_key=object_key,
                    hashed_object_key_b64=None,
                    classification=adapter.classification,
                    schema_version=stored.schema_version,
                    written_at=written_at,
                    envelope_json=envelope_json,
                )
            )
    records.sort(key=lambda record: (record.namespace, record.object_key or record.hashed_object_key_b64 or ""))
    bundle = ArchiveBundle(
        bundle_schema_version=ARCHIVE_BUNDLE_SCHEMA_VERSION,
        bundle_id=bundle_id or uuid.uuid4().hex,
        created_at=datetime.now(UTC),
        records=tuple(records),
    )
    _log.info(
        "archive export: produced bundle %s covering %d record(s) across %d namespace(s)",
        bundle.bundle_id,
        len(bundle.records),
        len(adapters),
    )
    return bundle


__all__ = ["create_archive"]
