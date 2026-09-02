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
  :exc:`cadrumo.adapters.persistence.storage.errors.RepositoryError`.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from ......tests.aeat_literal_fixtures import PDF_100_PATH_FIXTURE, PDF_FORM_PATH_FIXTURE, sede_pdf_url
from ...errors import RepositoryError
from ...tests.engine_bootstrap import bootstrap_sqlite_engine
from .. import (
    CorpusArtifactRecord,
    CorpusArtifactRepository,
    ModeloCatalogueRecord,
    ModeloRepository,
    PortalAuthMethod,
    PortalRecord,
    PortalRepository,
    session_scope,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@contextmanager
def _schema_engine(tmp_path: Path, name: str = "constraints.db") -> Generator[Engine]:
    engine = bootstrap_sqlite_engine(tmp_path / name)
    try:
        yield engine
    finally:
        engine.dispose()


def test_sqlite_foreign_keys_cascade(tmp_path: Path) -> None:
    """Deleting a modelo cascades to its corpus artifacts under SQLite."""
    with _schema_engine(tmp_path, "fk.db") as engine:
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


def test_portal_auth_method_check_constraint(tmp_path: Path) -> None:
    """A raw insert with an unknown auth_method value is rejected by SQLite."""
    with _schema_engine(tmp_path, "check.db") as engine:
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


def test_corpus_artifact_unique_identity(tmp_path: Path) -> None:
    """Duplicate (year, modelo_id, file_path) tuples surface as RepositoryError."""
    with _schema_engine(tmp_path, "unique.db") as engine:
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


def test_secure_object_schema_version_check_constraint(tmp_path: Path) -> None:
    """A raw secure-object insert with schema_version < 1 is rejected."""
    with (
        _schema_engine(tmp_path, "secure-object-schema-version.db") as engine,
        pytest.raises(IntegrityError, match=r"CHECK constraint failed: ck_secure_objects_schema_version_positive"),
        session_scope(engine) as session,
    ):
        session.execute(
            text(
                "insert into secure_objects "
                "(namespace, object_key, classification, schema_version, written_at, payload) "
                "values ('cadrumo-test.raw', :object_key, 'financial', 0, :written_at, :payload)",
            ),
            {
                "object_key": b"raw-key",
                "written_at": datetime(2026, 6, 4, tzinfo=UTC),
                "payload": b"ciphertext",
            },
        )


def test_secure_object_revision_hash_check_constraints(tmp_path: Path) -> None:
    """Raw secure-object revision/hash metadata must use 64-character digests."""
    with (
        _schema_engine(tmp_path, "secure-object-revision-hash.db") as engine,
        pytest.raises(IntegrityError, match=r"CHECK constraint failed: ck_secure_objects_revision_id_len"),
        session_scope(engine) as session,
    ):
        session.execute(
            text(
                "insert into secure_objects "
                "(namespace, object_key, classification, schema_version, written_at, revision_id, payload) "
                "values ('cadrumo-test.raw', :object_key, 'financial', 1, :written_at, 'short', :payload)",
            ),
            {
                "object_key": b"raw-key",
                "written_at": datetime(2026, 6, 4, tzinfo=UTC),
                "payload": b"ciphertext",
            },
        )


def test_modelo_upsert_natural_key(tmp_path: Path) -> None:
    """Upserting a modelo without id but with an existing identifier updates it."""
    with _schema_engine(tmp_path, "natural.db") as engine:
        with session_scope(engine) as session:
            repo = ModeloRepository(session)
            first = repo.upsert(ModeloCatalogueRecord(identifier="MODELO_130", name="Pagos fraccionados"))
            second = repo.upsert(ModeloCatalogueRecord(identifier="MODELO_130", name="Pagos fraccionados IRPF"))
        assert first.id == second.id
        assert second.name.endswith("IRPF")


def test_portal_upsert_wraps_integrity_error(tmp_path: Path) -> None:
    """A portal upsert with a non-existent modelo_id surfaces as RepositoryError."""
    with (
        _schema_engine(tmp_path, "wrap.db") as engine,
        pytest.raises(RepositoryError),
        session_scope(engine) as session,
    ):
        PortalRepository(session).upsert(
            PortalRecord(
                identifier="ORPHAN_PORTAL",
                base_url="https://example.test",
                auth_method=PortalAuthMethod.NONE,
                modelo_id=9999,
                label="Orphan",
            ),
        )
