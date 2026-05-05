"""Encrypted SQL byte-object repository for sensitive application payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine, select
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
    object_key: str
    classification: SensitivityClass
    schema_version: int
    written_at: datetime
    payload: bytes


class SecureObjectRepository:
    """Repository over encrypted byte objects stored in the primary database."""

    def __init__(self, *, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()
        _orm.SecureObjectRow.__table__.create(self._engine, checkfirst=True)

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
            try:
                classification = SensitivityClass(row.classification)
            except ValueError as exc:
                raise ClassificationError(
                    f"secure object {namespace}/{object_key} has unknown classification {row.classification!r}",
                ) from exc
            if classification is not expected_class:
                raise ClassificationError(
                    f"secure object {namespace}/{object_key} has classification {classification}; "
                    f"consumer expected {expected_class}",
                )
            if row.schema_version > max_supported_version:
                raise EnvelopeVersionError(
                    f"secure object {namespace}/{object_key} is at version {row.schema_version}; "
                    f"consumer supports up to {max_supported_version}",
                )
            return SecureObjectRecord(
                namespace=row.namespace,
                object_key=row.object_key,
                classification=classification,
                schema_version=row.schema_version,
                written_at=row.written_at,
                payload=row.payload,
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
            row = session.execute(
                select(_orm.SecureObjectRow).where(
                    _orm.SecureObjectRow.namespace == namespace,
                    _orm.SecureObjectRow.object_key == object_key,
                )
            ).scalar_one_or_none()
            if row is None:
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
                row.classification = classification.value
                row.schema_version = schema_version
                row.written_at = written_at
                row.payload = payload
            try:
                session.flush()
            except IntegrityError as exc:
                raise RepositoryError(f"secure object upsert failed for {namespace}/{object_key}: {exc.orig}") from exc

    def delete(self, namespace: str, object_key: str) -> bool:
        """Delete one object if it exists."""

        with session_scope(self._engine) as session:
            row = session.execute(
                select(_orm.SecureObjectRow).where(
                    _orm.SecureObjectRow.namespace == namespace,
                    _orm.SecureObjectRow.object_key == object_key,
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            session.delete(row)
            return True

