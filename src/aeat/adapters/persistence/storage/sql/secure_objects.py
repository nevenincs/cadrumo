"""Encrypted SQL byte-object repository for sensitive application payloads."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import Engine, bindparam, delete, select, text, update
from sqlalchemy.exc import IntegrityError

from .....core.classification import SensitivityClass
from ..crypto._encrypted_columns import decrypt_encrypted_bytes_column
from ..errors import (
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
    RepositoryError,
)
from . import _orm
from .engine import get_engine
from .session import session_scope

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SecureObjectRecord:
    """One decrypted sensitive object loaded from the SQL backend."""

    namespace: str
    object_key: bytes
    classification: SensitivityClass
    schema_version: int
    written_at: datetime
    payload: bytes


@dataclass(frozen=True, slots=True)
class SecureObjectUnreadable:
    """One stored secure object that cannot be decrypted under the current master key.

    Surfaced by :meth:`SecureObjectRepository.iter_records_with_failures`
    so iterating consumers can count and report the unreadable subset
    rather than aborting on the first failure. The plaintext is
    cryptographically unrecoverable from this process — the master key
    under which the row was sealed is no longer available.
    """

    namespace: str
    row_id: int
    object_key: bytes
    classification: str
    schema_version: int
    written_at: datetime
    reason: str


SecureObjectListItem = SecureObjectRecord | SecureObjectUnreadable


class SecureObjectRepository:
    """Repository over encrypted byte objects stored in the primary database."""

    def __init__(self, *, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()
        cast(Any, _orm.SecureObjectRow.__table__).create(self._engine, checkfirst=True)

    def exists(self, namespace: str, object_key: str) -> bool:
        """Return whether ``namespace`` / ``object_key`` is present."""

        with session_scope(self._engine) as session:
            row_id = session.execute(
                select(_orm.SecureObjectRow.id).where(
                    _orm.SecureObjectRow.namespace == namespace,
                    _orm.SecureObjectRow.object_key == object_key,
                )
            ).scalar_one_or_none()
            return row_id is not None

    def exists_by_raw_key(self, namespace: str, hashed_object_key: bytes) -> bool:
        """Return whether ``namespace`` carries a row with this raw HMAC digest.

        Used by the archive restore pipeline when the natural key was
        not present in the source bundle (path-keyed namespaces). Same
        master-key constraint as :meth:`save_with_raw_key`.
        """
        if len(hashed_object_key) != 32:
            raise ValueError(
                f"hashed_object_key must be 32 bytes; got {len(hashed_object_key)}",
            )
        with session_scope(self._engine) as session:
            row_id = session.execute(
                select(_orm.SecureObjectRow.id).where(
                    _orm.SecureObjectRow.namespace == namespace,
                    _orm.SecureObjectRow.object_key == hashed_object_key,
                )
            ).scalar_one_or_none()
            return row_id is not None

    def list_keys(self, namespace: str) -> tuple[str, ...]:
        """Return stored lookup digests under ``namespace`` as hex strings.

        Natural object keys are HMAC digested before storage and cannot be
        recovered from the index. Domain repositories that need natural IDs
        should iterate :meth:`list_records` and read IDs from decrypted
        payloads.
        """

        with session_scope(self._engine) as session:
            rows = session.execute(
                select(_orm.SecureObjectRow.object_key)
                .where(_orm.SecureObjectRow.namespace == namespace)
                .order_by(_orm.SecureObjectRow.object_key)
            ).scalars()
            return tuple(bytes(row).hex() for row in rows)

    def list_records(
        self,
        namespace: str,
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
    ) -> Iterator[SecureObjectRecord]:
        """Yield every decryptable object under ``namespace``.

        Rows whose payload cannot be decrypted under the current master
        key are skipped; one ``WARNING`` log line summarises the count at
        the end of the iteration. Use :meth:`iter_records_with_failures`
        to receive a typed per-row outcome instead of skipping silently.
        """
        unreadable = 0
        for item in self.iter_records_with_failures(
            namespace,
            expected_class=expected_class,
            max_supported_version=max_supported_version,
        ):
            if isinstance(item, SecureObjectRecord):
                yield item
            else:
                unreadable += 1
        if unreadable > 0:
            _log.warning(
                "secure_objects: skipped %d unreadable row(s) in namespace %s; "
                "the master key under which they were sealed is no longer available "
                "(run 'aeat config doctor' for details).",
                unreadable,
                namespace,
            )

    def iter_records_with_failures(
        self,
        namespace: str,
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
    ) -> Iterator[SecureObjectListItem]:
        """Yield a typed outcome per stored row under ``namespace``.

        Each row is represented by either a :class:`SecureObjectRecord`
        (the row decrypts cleanly and matches the consumer's classification
        and schema-version contract) or a :class:`SecureObjectUnreadable`
        (the on-wire ciphertext exists but cannot be decrypted under the
        current master key, or its metadata fails the consumer's contract).

        The iterator is fault-isolated: a failure on row ``N`` does not
        prevent rows ``> N`` from being inspected. Consumers count the
        failures and decide how to report them; nothing is auto-deleted.
        """
        with session_scope(self._engine) as session:
            stmt = (
                text(
                    "SELECT id, object_key, classification, schema_version, "
                    "written_at, payload "
                    "FROM secure_objects WHERE namespace = :namespace "
                    "ORDER BY object_key"
                )
                .bindparams(bindparam("namespace", value=namespace))
                .columns(
                    id=_orm.SecureObjectRow.__table__.c.id.type,
                    object_key=_orm.SecureObjectRow.__table__.c.object_key.type,
                    classification=_orm.SecureObjectRow.__table__.c.classification.type,
                    schema_version=_orm.SecureObjectRow.__table__.c.schema_version.type,
                    written_at=_orm.SecureObjectRow.__table__.c.written_at.type,
                )
            )
            rows = session.execute(stmt).all()
        for raw in rows:
            row_id = int(raw.id)
            object_key = bytes(raw.object_key)
            classification_str = str(raw.classification)
            schema_version = int(raw.schema_version)
            written_at = raw.written_at
            payload_wire = bytes(raw.payload)
            try:
                classification = SensitivityClass(classification_str)
            except ValueError:
                yield SecureObjectUnreadable(
                    namespace=namespace,
                    row_id=row_id,
                    object_key=object_key,
                    classification=classification_str,
                    schema_version=schema_version,
                    written_at=written_at,
                    reason=f"unknown classification {classification_str!r}",
                )
                continue
            if classification is not expected_class:
                raise ClassificationError(
                    f"secure object {namespace}/{object_key.hex()} has classification "
                    f"{classification}; consumer expected {expected_class}",
                )
            if schema_version > max_supported_version:
                raise EnvelopeVersionError(
                    f"secure object {namespace}/{object_key.hex()} is at version "
                    f"{schema_version}; consumer supports up to {max_supported_version}",
                )
            try:
                payload_plain = decrypt_encrypted_bytes_column(payload_wire)
            except DecryptionError as exc:
                yield SecureObjectUnreadable(
                    namespace=namespace,
                    row_id=row_id,
                    object_key=object_key,
                    classification=classification_str,
                    schema_version=schema_version,
                    written_at=written_at,
                    reason=str(exc),
                )
                continue
            yield SecureObjectRecord(
                namespace=namespace,
                object_key=object_key,
                classification=classification,
                schema_version=schema_version,
                written_at=written_at,
                payload=payload_plain,
            )

    def load(
        self,
        namespace: str,
        object_key: str,
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
    ) -> SecureObjectRecord | None:
        """Load and decrypt one object, returning ``None`` when absent."""

        with session_scope(self._engine) as session:
            row = session.execute(
                select(_orm.SecureObjectRow).where(
                    _orm.SecureObjectRow.namespace == namespace,
                    _orm.SecureObjectRow.object_key == object_key,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return self._record_from_row(
                row,
                expected_class=expected_class,
                max_supported_version=max_supported_version,
            )

    def save(
        self,
        *,
        namespace: str,
        object_key: str,
        classification: SensitivityClass,
        schema_version: int,
        written_at: datetime,
        payload: bytes,
    ) -> None:
        """Encrypt and upsert one byte payload keyed by a natural string id.

        The natural ``object_key`` is HMAC-digested at the column
        boundary. To upsert against a pre-computed digest (e.g. when
        restoring an archive bundle whose natural key was lost in the
        original HMAC), use :meth:`save_with_raw_key` instead.
        """
        self._save_internal(
            namespace=namespace,
            key=object_key,
            classification=classification,
            schema_version=schema_version,
            written_at=written_at,
            payload=payload,
        )

    def save_with_raw_key(
        self,
        *,
        namespace: str,
        hashed_object_key: bytes,
        classification: SensitivityClass,
        schema_version: int,
        written_at: datetime,
        payload: bytes,
    ) -> None:
        """Encrypt and upsert one byte payload keyed by a pre-computed digest.

        The 32-byte ``hashed_object_key`` is passed straight through
        the :class:`HashedLookup` column without re-hashing. Used by
        the archive restore path to round-trip rows whose natural key
        is not present in the bundle (e.g. the path-keyed setup-profile
        and inventory namespaces).

        Args:
            namespace: The :class:`SecureObjectRepository` namespace.
            hashed_object_key: 32 raw HMAC-SHA256 bytes (the digest
                produced by :meth:`HashedLookup.compute` under the
                same master key the row was originally written with).
            classification: Sensitivity class to upsert at.
            schema_version: Envelope schema version captured on the row.
            written_at: Timezone-aware datetime captured on the row.
            payload: Plaintext envelope bytes (the column encrypts).

        Raises:
            :exc:`ValueError`: If ``hashed_object_key`` is not exactly
                32 bytes (the size :class:`HashedLookup` requires).
            :exc:`RepositoryError`: On underlying SQL integrity errors.
        """
        if len(hashed_object_key) != 32:
            raise ValueError(
                f"hashed_object_key must be 32 bytes; got {len(hashed_object_key)}",
            )
        self._save_internal(
            namespace=namespace,
            key=hashed_object_key,
            classification=classification,
            schema_version=schema_version,
            written_at=written_at,
            payload=payload,
        )

    def _save_internal(
        self,
        *,
        namespace: str,
        key: str | bytes,
        classification: SensitivityClass,
        schema_version: int,
        written_at: datetime,
        payload: bytes,
    ) -> None:
        """Shared upsert backing :meth:`save` and :meth:`save_with_raw_key`."""
        with session_scope(self._engine) as session:
            row_id = session.execute(
                select(_orm.SecureObjectRow.id).where(
                    _orm.SecureObjectRow.namespace == namespace,
                    _orm.SecureObjectRow.object_key == key,
                )
            ).scalar_one_or_none()
            if row_id is None:
                row = _orm.SecureObjectRow(
                    namespace=namespace,
                    object_key=key,
                    classification=classification.value,
                    schema_version=schema_version,
                    written_at=written_at,
                    payload=payload,
                )
                session.add(row)
            else:
                session.execute(
                    update(_orm.SecureObjectRow)
                    .where(_orm.SecureObjectRow.id == row_id)
                    .values(
                        classification=classification.value,
                        schema_version=schema_version,
                        written_at=written_at,
                        payload=payload,
                    )
                )
            try:
                session.flush()
            except IntegrityError as exc:
                raise RepositoryError(
                    f"secure object upsert failed for {namespace}/<key>: {exc.orig}",
                ) from exc

    def delete(self, namespace: str, object_key: str) -> bool:
        """Delete one object if it exists."""

        with session_scope(self._engine) as session:
            row_id = session.execute(
                select(_orm.SecureObjectRow.id).where(
                    _orm.SecureObjectRow.namespace == namespace,
                    _orm.SecureObjectRow.object_key == object_key,
                )
            ).scalar_one_or_none()
            if row_id is None:
                return False
            session.execute(delete(_orm.SecureObjectRow).where(_orm.SecureObjectRow.id == row_id))
            return True

    def _record_from_row(
        self,
        row: _orm.SecureObjectRow,
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
    ) -> SecureObjectRecord:
        try:
            classification = SensitivityClass(row.classification)
        except ValueError as exc:
            raise ClassificationError(
                f"secure object {row.namespace}/{bytes(row.object_key).hex()} "
                f"has unknown classification {row.classification!r}",
            ) from exc
        if classification is not expected_class:
            raise ClassificationError(
                f"secure object {row.namespace}/{bytes(row.object_key).hex()} has classification {classification}; "
                f"consumer expected {expected_class}",
            )
        if row.schema_version > max_supported_version:
            raise EnvelopeVersionError(
                f"secure object {row.namespace}/{bytes(row.object_key).hex()} is at version {row.schema_version}; "
                f"consumer supports up to {max_supported_version}",
            )
        return SecureObjectRecord(
            namespace=row.namespace,
            object_key=bytes(row.object_key),
            classification=classification,
            schema_version=row.schema_version,
            written_at=row.written_at,
            payload=row.payload,
        )
