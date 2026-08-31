"""Typed repositories for the public storage records.

Each repository exposes a small, explicit CRUD surface against its pydantic
record type from :mod:`adapters.persistence.storage.sql.records`. The
repositories translate between the public records and the internal
SQLAlchemy mapper classes from :mod:`adapters.persistence.storage.sql._orm`
on every boundary crossing, raising
:exc:`~adapters.persistence.storage.RepositoryError` on integrity
violations or missing-row lookups.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import override

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .....core.logging import get_logger
from ..errors import RepositoryError
from . import orm as _orm
from .records import CorpusArtifactRecord, ModeloCatalogueRecord, PortalAuthMethod, PortalRecord

_log = get_logger(__name__)


def _flush_or_wrap(session: Session, kind: str) -> None:
    """Flush ``session`` and wrap ``IntegrityError`` as :exc:`RepositoryError`.

    Args:
        session: The active :class:`~sqlalchemy.orm.Session` to flush.
        kind: Short label describing the record type for the error message.

    Raises:
        RepositoryError: When the flush raises ``IntegrityError``.
    """
    try:
        session.flush()
    except IntegrityError as exc:
        _log.warning(
            "repository: integrity violation during %s",
            kind,
            exc_info=True,
        )
        raise RepositoryError(f"integrity violation during {kind} operation: {exc.orig}") from exc


class SqlRecordRepository[RecordT](ABC):
    """Abstract base class for every typed record repository.

    Subclasses own a single SQLAlchemy mapper class and are responsible for
    converting between that mapper class and a pydantic record type.
    """

    def __init__(self, session: Session) -> None:
        """Bind this repository to an active SQLAlchemy session.

        Args:
            session: An open :class:`~sqlalchemy.orm.Session`.
        """
        self.session = session

    @abstractmethod
    def list_all(self) -> list[RecordT]:
        """Return every row as a typed pydantic record, ordered by primary key."""

    @abstractmethod
    def get(self, record_id: int) -> RecordT:
        """Return a single row by primary key.

        Args:
            record_id: Primary-key value to fetch.

        Returns:
            The typed record matching ``record_id``.
        """

    @abstractmethod
    def upsert(self, record: RecordT) -> RecordT:
        """Insert or update ``record`` and return the persisted value.

        Args:
            record: Pydantic record to persist. ``id`` selects update mode;
                otherwise a natural-key lookup decides between insert and
                update.

        Returns:
            The persisted typed record reflecting the on-disk state.
        """

    @abstractmethod
    def delete(self, record_id: int) -> None:
        """Delete the row with ``record_id``.

        Args:
            record_id: Primary-key value to delete.

        Raises:
            :exc:`~adapters.persistence.storage.RepositoryError`:
                If no row with ``record_id`` exists.
        """


class ModeloRepository(SqlRecordRepository[ModeloCatalogueRecord]):
    """Repository for :class:`ModeloCatalogueRecord`."""

    @override
    def list_all(self) -> list[ModeloCatalogueRecord]:
        """Return every :class:`ModeloCatalogueRecord` in the table, ordered by surrogate id."""
        rows = self.session.execute(select(_orm.ModeloRow).order_by(_orm.ModeloRow.id)).scalars().all()
        return [self._to_record(row) for row in rows]

    @override
    def get(self, record_id: int) -> ModeloCatalogueRecord:
        """Return the record with surrogate id ``record_id``.

        Args:
            record_id: Surrogate primary-key value to look up.

        Returns:
            The matching :class:`ModeloCatalogueRecord`.

        Raises:
            RepositoryError: When no row matches.
        """
        row = self.session.get(_orm.ModeloRow, record_id)
        if row is None:
            raise RepositoryError(f"modelo id={record_id} not found")
        return self._to_record(row)

    @override
    def upsert(self, record: ModeloCatalogueRecord) -> ModeloCatalogueRecord:
        """Insert or update ``record`` and return the persisted :class:`ModeloCatalogueRecord`."""
        row: _orm.ModeloRow | None = None
        if record.id is not None:
            row = self.session.get(_orm.ModeloRow, record.id)
            if row is None:
                raise RepositoryError(f"modelo id={record.id} not found for update")
        else:
            row = self.session.execute(
                select(_orm.ModeloRow).where(_orm.ModeloRow.identifier == record.identifier),
            ).scalar_one_or_none()
        if row is None:
            row = _orm.ModeloRow(identifier=record.identifier, name=record.name)
            self.session.add(row)
        else:
            row.identifier = record.identifier
            row.name = record.name
        _flush_or_wrap(self.session, "modelo")
        return self._to_record(row)

    @override
    def delete(self, record_id: int) -> None:
        """Delete the record with surrogate id ``record_id``."""
        row = self.session.get(_orm.ModeloRow, record_id)
        if row is None:
            raise RepositoryError(f"modelo id={record_id} not found")
        self.session.delete(row)
        _flush_or_wrap(self.session, "modelo")

    @staticmethod
    def _to_record(row: _orm.ModeloRow) -> ModeloCatalogueRecord:
        return ModeloCatalogueRecord(id=row.id, identifier=row.identifier, name=row.name)


class PortalRepository(SqlRecordRepository[PortalRecord]):
    """Repository for :class:`PortalRecord`."""

    @override
    def list_all(self) -> list[PortalRecord]:
        """Return every :class:`PortalRecord` in the table, ordered by surrogate id."""
        rows = self.session.execute(select(_orm.PortalOrmRow).order_by(_orm.PortalOrmRow.id)).scalars().all()
        return [self._to_record(row) for row in rows]

    @override
    def get(self, record_id: int) -> PortalRecord:
        """Return the record with surrogate id ``record_id``.

        Args:
            record_id: Surrogate primary-key value to look up.

        Returns:
            The matching :class:`PortalRecord`.

        Raises:
            RepositoryError: When no row matches.
        """
        row = self.session.get(_orm.PortalOrmRow, record_id)
        if row is None:
            raise RepositoryError(f"portal id={record_id} not found")
        return self._to_record(row)

    @override
    def upsert(self, record: PortalRecord) -> PortalRecord:
        """Insert or update ``record`` and return the persisted :class:`PortalRecord`."""
        row: _orm.PortalOrmRow | None = None
        if record.id is not None:
            row = self.session.get(_orm.PortalOrmRow, record.id)
            if row is None:
                raise RepositoryError(f"portal id={record.id} not found for update")
        else:
            row = self.session.execute(
                select(_orm.PortalOrmRow).where(_orm.PortalOrmRow.identifier == record.identifier),
            ).scalar_one_or_none()
        if row is None:
            row = _orm.PortalOrmRow(
                identifier=record.identifier,
                base_url=record.base_url,
                auth_method=record.auth_method.value,
                modelo_id=record.modelo_id,
                label=record.label,
            )
            self.session.add(row)
        else:
            row.identifier = record.identifier
            row.base_url = record.base_url
            row.auth_method = record.auth_method.value
            row.modelo_id = record.modelo_id
            row.label = record.label
        _flush_or_wrap(self.session, "portal")
        return self._to_record(row)

    @override
    def delete(self, record_id: int) -> None:
        """Delete the record with surrogate id ``record_id``."""
        row = self.session.get(_orm.PortalOrmRow, record_id)
        if row is None:
            raise RepositoryError(f"portal id={record_id} not found")
        self.session.delete(row)
        _flush_or_wrap(self.session, "portal")

    @staticmethod
    def _to_record(row: _orm.PortalOrmRow) -> PortalRecord:
        try:
            auth_method = PortalAuthMethod(row.auth_method)
        except ValueError as exc:
            raise RepositoryError(
                f"portal id={row.id} has unknown auth_method={row.auth_method!r}",
            ) from exc
        return PortalRecord(
            id=row.id,
            identifier=row.identifier,
            base_url=row.base_url,
            auth_method=auth_method,
            modelo_id=row.modelo_id,
            label=row.label,
        )


class CorpusArtifactRepository(SqlRecordRepository[CorpusArtifactRecord]):
    """Repository for :class:`CorpusArtifactRecord`."""

    @override
    def list_all(self) -> list[CorpusArtifactRecord]:
        """Return every :class:`CorpusArtifactRecord` in the table, ordered by surrogate id."""
        rows = self.session.execute(select(_orm.CorpusArtifactRow).order_by(_orm.CorpusArtifactRow.id)).scalars().all()
        return [self._to_record(row) for row in rows]

    @override
    def get(self, record_id: int) -> CorpusArtifactRecord:
        """Return the record with surrogate id ``record_id``.

        Args:
            record_id: Surrogate primary-key value to look up.

        Returns:
            The matching :class:`CorpusArtifactRecord`.

        Raises:
            RepositoryError: When no row matches.
        """
        row = self.session.get(_orm.CorpusArtifactRow, record_id)
        if row is None:
            raise RepositoryError(f"corpus_artifact id={record_id} not found")
        return self._to_record(row)

    @override
    def upsert(self, record: CorpusArtifactRecord) -> CorpusArtifactRecord:
        """Insert or update ``record`` and return the persisted :class:`CorpusArtifactRecord`."""
        row: _orm.CorpusArtifactRow | None = None
        if record.id is not None:
            row = self.session.get(_orm.CorpusArtifactRow, record.id)
            if row is None:
                raise RepositoryError(f"corpus_artifact id={record.id} not found for update")
        else:
            row = self.session.execute(
                select(_orm.CorpusArtifactRow).where(
                    _orm.CorpusArtifactRow.year == record.year,
                    _orm.CorpusArtifactRow.modelo_id == record.modelo_id,
                    _orm.CorpusArtifactRow.file_path == record.file_path,
                ),
            ).scalar_one_or_none()
        if row is None:
            row = _orm.CorpusArtifactRow(
                year=record.year,
                modelo_id=record.modelo_id,
                file_path=record.file_path,
                sha256=record.sha256,
                source_url=record.source_url,
                fetched_at=record.fetched_at,
            )
            self.session.add(row)
        else:
            row.year = record.year
            row.modelo_id = record.modelo_id
            row.file_path = record.file_path
            row.sha256 = record.sha256
            row.source_url = record.source_url
            row.fetched_at = record.fetched_at
        _flush_or_wrap(self.session, "corpus_artifact")
        return self._to_record(row)

    @override
    def delete(self, record_id: int) -> None:
        """Delete the record with surrogate id ``record_id``."""
        row = self.session.get(_orm.CorpusArtifactRow, record_id)
        if row is None:
            raise RepositoryError(f"corpus_artifact id={record_id} not found")
        self.session.delete(row)
        _flush_or_wrap(self.session, "corpus_artifact")

    @staticmethod
    def _to_record(row: _orm.CorpusArtifactRow) -> CorpusArtifactRecord:
        return CorpusArtifactRecord(
            id=row.id,
            year=row.year,
            modelo_id=row.modelo_id,
            file_path=row.file_path,
            sha256=row.sha256,
            source_url=row.source_url,
            fetched_at=row.fetched_at,
        )
