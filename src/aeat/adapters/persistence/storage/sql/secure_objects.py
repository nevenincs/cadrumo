"""Encrypted SQL byte-object repository for sensitive application payloads."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import Engine, delete, select, update
from sqlalchemy.exc import IntegrityError

from .....core.classification import SensitivityClass
from ..errors import ClassificationError, EnvelopeVersionError, RepositoryError
from . import _orm
from .engine import get_engine
from .session import session_scope


@dataclass(frozen=True, slots=True)
class SecureObjectRecord:
    """One decrypted sensitive object loaded from the SQL backend."""

    namespace: str
    object_key: bytes
    classification: SensitivityClass
    schema_version: int
    written_at: datetime
    payload: bytes


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
        """Yield every decrypted object under ``namespace``."""

        with session_scope(self._engine) as session:
            rows = tuple(
                session.execute(
                    select(_orm.SecureObjectRow)
                    .where(_orm.SecureObjectRow.namespace == namespace)
                    .order_by(_orm.SecureObjectRow.object_key)
                ).scalars()
            )
        for row in rows:
            yield self._record_from_row(
                row,
                expected_class=expected_class,
                max_supported_version=max_supported_version,
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
        """Encrypt and upsert one byte payload."""

        with session_scope(self._engine) as session:
            row_id = session.execute(
                select(_orm.SecureObjectRow.id).where(
                    _orm.SecureObjectRow.namespace == namespace,
                    _orm.SecureObjectRow.object_key == object_key,
                )
            ).scalar_one_or_none()
            if row_id is None:
                row = _orm.SecureObjectRow(
                    namespace=namespace,
                    object_key=object_key,
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
                raise RepositoryError(f"secure object upsert failed for {namespace}/{object_key}: {exc.orig}") from exc

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
