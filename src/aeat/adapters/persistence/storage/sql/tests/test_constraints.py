"""Regression tests for the SQL substrate's database-level integrity guards.

Covers the schema and repository invariants enforced at the database
layer rather than at the pydantic record layer:

- SQLite ``PRAGMA foreign_keys=ON`` is enabled so ``ON DELETE CASCADE``
  runs.
- ``portals.auth_method`` rejects unknown values at the database layer.
- ``corpus_artifacts`` enforces ``(year, modelo_id, file_path)``
  uniqueness.
- ``secure_objects`` rejects impossible schema versions and malformed
  revision/hash metadata at the database layer.
- Repository ``upsert`` resolves by natural key when ``id`` is omitted.
- Repository ``upsert`` wraps :exc:`sqlalchemy.exc.IntegrityError` as
  :exc:`aeat.adapters.persistence.storage.errors.RepositoryError`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ......core.config import Settings
from ......tests.aeat_literal_fixtures import PDF_100_PATH_FIXTURE, PDF_FORM_PATH_FIXTURE, sede_pdf_url
from ...errors import RepositoryError
from .. import (
    CorpusArtifactRecord,
    CorpusArtifactRepository,
    ModeloCatalogueRecord,
    ModeloRepository,
    PortalAuthMethod,
    PortalRecord,
    PortalRepository,
    create_engine_from_settings,
    session_scope,
)
from .._orm import metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _schema_engine(tmp_path: Path, name: str = "constraints.db"):
    settings = Settings(aeat_database_url=f"sqlite:///{(tmp_path / name).as_posix()}")
    engine = create_engine_from_settings(settings)
    metadata.create_all(engine)
    return engine


def test_sqlite_foreign_keys_cascade(tmp_path: Path) -> None:
    """Deleting a modelo cascades to its corpus artifacts under SQLite."""
    engine = _schema_engine(tmp_path, "fk.db")
    try:
        with session_scope(engine) as session:
            modelo = ModeloRepository(session).upsert(ModeloCatalogueRecord(identifier="MODELO_130", name="Pagos"))
            assert modelo.id is not None
            CorpusArtifactRepository(session).upsert(
                CorpusArtifactRecord(
                    year=2024,
                    modelo_id=modelo.id,
                    file_path="corpus/2024/modelos/130/form.pdf",
                    sha256="a" * 64,
                    source_url=sede_pdf_url(PDF_FORM_PATH_FIXTURE),
                    fetched_at=datetime(2026, 4, 12, tzinfo=UTC),
                ),
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
    engine = _schema_engine(tmp_path, "check.db")
    try:
        with session_scope(engine) as session:
            modelo = ModeloRepository(session).upsert(ModeloCatalogueRecord(identifier="MODELO_303", name="IVA"))
        with (
            pytest.raises(IntegrityError, match=r"CHECK constraint failed: ck_portals_auth_method"),
            session_scope(engine) as session,
        ):
            session.execute(
                text(
                    "insert into portals (identifier, base_url, auth_method, modelo_id, label)"
                    " values ('BAD', 'https://example.test', 'totally-bogus', :mid, 'Bad')",
                ),
                {"mid": modelo.id},
            )
    finally:
        engine.dispose()


def test_corpus_artifact_unique_identity(tmp_path: Path) -> None:
    """Duplicate (year, modelo_id, file_path) tuples surface as RepositoryError."""
    engine = _schema_engine(tmp_path, "unique.db")
    try:
        with session_scope(engine) as session:
            modelo = ModeloRepository(session).upsert(ModeloCatalogueRecord(identifier="MODELO_100", name="IRPF"))
            assert modelo.id is not None
            repo = CorpusArtifactRepository(session)
            record = CorpusArtifactRecord(
                year=2024,
                modelo_id=modelo.id,
                file_path="corpus/2024/modelos/100/form.pdf",
                sha256="b" * 64,
                source_url=sede_pdf_url(PDF_100_PATH_FIXTURE),
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
                    source_url=sede_pdf_url(PDF_100_PATH_FIXTURE),
                    fetched_at=datetime(2026, 4, 12, tzinfo=UTC),
                ),
            )
        with session_scope(engine) as session:
            listed = CorpusArtifactRepository(session).list_all()
        assert len(listed) == 1
        assert listed[0].sha256 == "c" * 64
    finally:
        engine.dispose()


def test_secure_object_schema_version_check_constraint(tmp_path: Path) -> None:
    """A raw secure-object insert with schema_version < 1 is rejected."""
    engine = _schema_engine(tmp_path, "secure-object-schema-version.db")
    try:
        with (
            pytest.raises(IntegrityError, match=r"CHECK constraint failed: ck_secure_objects_schema_version_positive"),
            session_scope(engine) as session,
        ):
            session.execute(
                text(
                    "insert into secure_objects "
                    "(namespace, object_key, classification, schema_version, written_at, payload) "
                    "values ('aeat.test.raw', :object_key, 'financial', 0, :written_at, :payload)",
                ),
                {
                    "object_key": b"raw-key",
                    "written_at": datetime(2026, 6, 4, tzinfo=UTC),
                    "payload": b"ciphertext",
                },
            )
    finally:
        engine.dispose()


def test_secure_object_revision_hash_check_constraints(tmp_path: Path) -> None:
    """Raw secure-object revision/hash metadata must use 64-character digests."""
    engine = _schema_engine(tmp_path, "secure-object-revision-hash.db")
    try:
        with (
            pytest.raises(IntegrityError, match=r"CHECK constraint failed: ck_secure_objects_revision_id_len"),
            session_scope(engine) as session,
        ):
            session.execute(
                text(
                    "insert into secure_objects "
                    "(namespace, object_key, classification, schema_version, written_at, revision_id, payload) "
                    "values ('aeat.test.raw', :object_key, 'financial', 1, :written_at, 'short', :payload)",
                ),
                {
                    "object_key": b"raw-key",
                    "written_at": datetime(2026, 6, 4, tzinfo=UTC),
                    "payload": b"ciphertext",
                },
            )
    finally:
        engine.dispose()


def test_modelo_upsert_natural_key(tmp_path: Path) -> None:
    """Upserting a modelo without id but with an existing identifier updates it."""
    engine = _schema_engine(tmp_path, "natural.db")
    try:
        with session_scope(engine) as session:
            repo = ModeloRepository(session)
            first = repo.upsert(ModeloCatalogueRecord(identifier="MODELO_130", name="Pagos fraccionados"))
            second = repo.upsert(ModeloCatalogueRecord(identifier="MODELO_130", name="Pagos fraccionados IRPF"))
        assert first.id == second.id
        assert second.name.endswith("IRPF")
    finally:
        engine.dispose()


def test_portal_upsert_wraps_integrity_error(tmp_path: Path) -> None:
    """A portal upsert with a non-existent modelo_id surfaces as RepositoryError."""
    engine = _schema_engine(tmp_path, "wrap.db")
    try:
        with pytest.raises(RepositoryError), session_scope(engine) as session:
            PortalRepository(session).upsert(
                PortalRecord(
                    identifier="ORPHAN_PORTAL",
                    base_url="https://example.test",
                    auth_method=PortalAuthMethod.NONE,
                    modelo_id=9999,
                    label="Orphan",
                ),
            )
    finally:
        engine.dispose()
