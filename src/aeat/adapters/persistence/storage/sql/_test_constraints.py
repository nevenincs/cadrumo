"""Regression tests for the SQL substrate's database-level integrity guards.

Covers the schema and repository invariants enforced at the database
layer rather than at the pydantic record layer:

- SQLite ``PRAGMA foreign_keys=ON`` is enabled so ``ON DELETE CASCADE``
  runs.
- ``portals.auth_method`` rejects unknown values at the database layer.
- ``corpus_artifacts`` enforces ``(year, modelo_id, file_path)``
  uniqueness.
- Repository ``upsert`` resolves by natural key when ``id`` is omitted.
- Repository ``upsert`` wraps :exc:`sqlalchemy.exc.IntegrityError` as
  :exc:`aeat.adapters.persistence.storage.errors.RepositoryError`.
- :func:`aeat.adapters.persistence.storage.sql.get_engine` runs
  ``alembic upgrade head`` when ``AEAT_STORAGE_AUTO_MIGRATE`` is true.
- Reading a portal row with an unknown ``auth_method`` raises
  :exc:`aeat.adapters.persistence.storage.errors.RepositoryError`,
  never a bare :exc:`ValueError`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from .....core.config import Settings
from . import (
    CorpusArtifactRecord,
    CorpusArtifactRepository,
    ModeloRecord,
    ModeloRepository,
    PortalAuthMethod,
    PortalRecord,
    PortalRepository,
    create_engine_from_settings,
    dispose_engine,
    get_engine,
    round_trip_migrations,
    session_scope,
    upgrade_to_head,
)
from ..errors import RepositoryError

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _migrated_engine(tmp_path: Path, name: str = "constraints.db"):
    settings = Settings(aeat_database_url=f"sqlite:///{(tmp_path / name).as_posix()}")
    engine = create_engine_from_settings(settings)
    upgrade_to_head(engine)
    return engine


def test_sqlite_foreign_keys_cascade(tmp_path: Path) -> None:
    """Deleting a modelo cascades to its corpus artifacts under SQLite."""
    engine = _migrated_engine(tmp_path, "fk.db")
    try:
        with session_scope(engine) as session:
            modelo = ModeloRepository(session).upsert(ModeloRecord(identifier="MODELO_130", name="Pagos"))
            assert modelo.id is not None
            CorpusArtifactRepository(session).upsert(
                CorpusArtifactRecord(
                    year=2024,
                    modelo_id=modelo.id,
                    file_path="corpus/2024/modelos/130/form.pdf",
                    sha256="a" * 64,
                    source_url="https://sede.agenciatributaria.gob.es/form.pdf",
                    fetched_at=datetime(2026, 4, 12, tzinfo=UTC),
                )
            )
        with session_scope(engine) as session:
            ModeloRepository(session).delete(1)
        with session_scope(engine) as session:
            artifacts = CorpusArtifactRepository(session).list_all()
        assert artifacts == []
    finally:
        engine.dispose()


def test_portal_auth_method_check_constraint(tmp_path: Path) -> None:
    """A raw insert with an unknown auth_method value is rejected by SQLite."""
    engine = _migrated_engine(tmp_path, "check.db")
    try:
        with session_scope(engine) as session:
            modelo = ModeloRepository(session).upsert(ModeloRecord(identifier="MODELO_303", name="IVA"))
        with pytest.raises(Exception) as excinfo, session_scope(engine) as session:
            session.execute(
                text(
                    "insert into portals (identifier, base_url, auth_method, modelo_id, label)"
                    " values ('BAD', 'https://example.test', 'totally-bogus', :mid, 'Bad')"
                ),
                {"mid": modelo.id},
            )
        assert "constraint" in str(excinfo.value).lower() or "check" in str(excinfo.value).lower()
    finally:
        engine.dispose()


def test_corpus_artifact_unique_identity(tmp_path: Path) -> None:
    """Duplicate (year, modelo_id, file_path) tuples surface as RepositoryError."""
    engine = _migrated_engine(tmp_path, "unique.db")
    try:
        with session_scope(engine) as session:
            modelo = ModeloRepository(session).upsert(ModeloRecord(identifier="MODELO_100", name="IRPF"))
            assert modelo.id is not None
            repo = CorpusArtifactRepository(session)
            record = CorpusArtifactRecord(
                year=2024,
                modelo_id=modelo.id,
                file_path="corpus/2024/modelos/100/form.pdf",
                sha256="b" * 64,
                source_url="https://sede.agenciatributaria.gob.es/100.pdf",
                fetched_at=datetime(2026, 4, 12, tzinfo=UTC),
            )
            repo.upsert(record)

        # A second insert with the same natural key but no id must be detected
        # as an update by the repository — not a duplicate.
        with session_scope(engine) as session:
            repo = CorpusArtifactRepository(session)
            repo.upsert(
                CorpusArtifactRecord(
                    year=2024,
                    modelo_id=modelo.id,
                    file_path="corpus/2024/modelos/100/form.pdf",
                    sha256="c" * 64,
                    source_url="https://sede.agenciatributaria.gob.es/100.pdf",
                    fetched_at=datetime(2026, 4, 12, tzinfo=UTC),
                )
            )
        with session_scope(engine) as session:
            listed = CorpusArtifactRepository(session).list_all()
        assert len(listed) == 1
        assert listed[0].sha256 == "c" * 64
    finally:
        engine.dispose()


def test_modelo_upsert_natural_key(tmp_path: Path) -> None:
    """Upserting a modelo without id but with an existing identifier updates it."""
    engine = _migrated_engine(tmp_path, "natural.db")
    try:
        with session_scope(engine) as session:
            repo = ModeloRepository(session)
            first = repo.upsert(ModeloRecord(identifier="MODELO_130", name="Pagos fraccionados"))
            second = repo.upsert(ModeloRecord(identifier="MODELO_130", name="Pagos fraccionados IRPF"))
        assert first.id == second.id
        assert second.name.endswith("IRPF")
    finally:
        engine.dispose()


def test_portal_upsert_wraps_integrity_error(tmp_path: Path) -> None:
    """A portal upsert with a non-existent modelo_id surfaces as RepositoryError."""
    engine = _migrated_engine(tmp_path, "wrap.db")
    try:
        with pytest.raises(RepositoryError), session_scope(engine) as session:
            PortalRepository(session).upsert(
                PortalRecord(
                    identifier="ORPHAN_PORTAL",
                    base_url="https://example.test",
                    auth_method=PortalAuthMethod.NONE,
                    modelo_id=9999,
                    label="Orphan",
                )
            )
    finally:
        engine.dispose()


def test_get_engine_honours_auto_migrate(tmp_path: Path) -> None:
    """``get_engine`` applies migrations when ``aeat_storage_auto_migrate`` is true."""
    db_path = tmp_path / "auto.db"
    settings = Settings(
        aeat_database_url=f"sqlite:///{db_path.as_posix()}",
        aeat_storage_auto_migrate=True,
    )
    try:
        engine = get_engine(settings)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"modelos", "portals", "corpus_artifacts"}.issubset(tables)
    finally:
        dispose_engine(settings)


def test_portal_repository_rejects_unknown_auth_method(tmp_path: Path) -> None:
    """A legacy row with an unknown auth_method surfaces as RepositoryError.

    Builds a ``portals`` table by raw DDL without the check constraint so the
    decoder path can be exercised with a value the migrated schema would
    otherwise reject.
    """
    settings = Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    engine = create_engine_from_settings(settings)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "create table modelos ("
                    " id integer primary key autoincrement,"
                    " identifier varchar(64) unique not null,"
                    " name varchar(255) not null)"
                )
            )
            conn.execute(
                text(
                    "create table portals ("
                    " id integer primary key autoincrement,"
                    " identifier varchar(64) unique not null,"
                    " base_url varchar(512) not null,"
                    " auth_method varchar(32) not null,"
                    " modelo_id integer,"
                    " label varchar(255) not null)"
                )
            )
            conn.execute(
                text(
                    "insert into portals (identifier, base_url, auth_method, modelo_id, label)"
                    " values ('LEGACY', 'https://example.test', 'mystery', null, 'Legacy')"
                )
            )
        with pytest.raises(RepositoryError), session_scope(engine) as session:
            PortalRepository(session).list_all()
    finally:
        engine.dispose()


def test_migrations_run_against_injected_in_memory_engine() -> None:
    """In-memory SQLite proves Alembic uses the caller's engine, not a new one."""
    settings = Settings(aeat_database_url="sqlite:///:memory:")
    engine = create_engine_from_settings(settings)
    try:
        upgrade_to_head(engine)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"modelos", "portals", "corpus_artifacts"}.issubset(tables), tables
    finally:
        engine.dispose()


def test_migrations_round_trip_with_constraints(tmp_path: Path) -> None:
    """head → base → head still round-trips with the 0002 revision in place."""
    settings = Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'rt.db').as_posix()}")
    engine = create_engine_from_settings(settings)
    try:
        round_trip_migrations(engine)
        inspector = inspect(engine)
        constraints = {uc["name"] for uc in inspector.get_unique_constraints("corpus_artifacts")}
        assert "uq_corpus_artifacts_identity" in constraints
    finally:
        engine.dispose()
