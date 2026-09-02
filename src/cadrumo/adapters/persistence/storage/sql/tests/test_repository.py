"""Unit tests for the typed repositories in :mod:`cadrumo.adapters.persistence.storage.sql`.

Exercises CRUD round-trips through :class:`ModeloRepository`,
:class:`PortalRepository`, and :class:`CorpusArtifactRepository` against a
real SQLite engine to confirm pydantic record translation, foreign-key
integrity, and enum round-trip behaviour.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from ......tests.aeat_literal_fixtures import PDF_MODELO_130_2024_PATH_FIXTURE, aeat_url, sede_pdf_url
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
def _engine(tmp_path: Path) -> Generator[Engine]:
    engine = bootstrap_sqlite_engine(tmp_path / "repo.db")
    try:
        yield engine
    finally:
        engine.dispose()


def test_modelo_repository_crud_round_trip(tmp_path: Path) -> None:
    """Insert, read, update, and delete cycle returns pydantic records throughout."""
    with _engine(tmp_path) as engine, session_scope(engine) as session:
        repo = ModeloRepository(session)
        created = repo.upsert(ModeloCatalogueRecord(identifier="MODELO_130", name="Pagos fraccionados"))
        assert isinstance(created, ModeloCatalogueRecord)
        assert created.id is not None

        fetched = repo.get(created.id)
        assert fetched == created
        assert repo.list_all() == [created]

        updated = repo.upsert(
            ModeloCatalogueRecord(id=created.id, identifier="MODELO_130", name="Pagos fraccionados IRPF"),
        )
        assert updated.name.endswith("IRPF")

        repo.delete(created.id)
        with pytest.raises(RepositoryError):
            repo.get(created.id)


def test_portal_repository_preserves_enum(tmp_path: Path) -> None:
    """:class:`PortalRepository` round-trips the ``auth_method`` enum without coercion."""
    with _engine(tmp_path) as engine, session_scope(engine) as session:
        modelo_repo = ModeloRepository(session)
        modelo = modelo_repo.upsert(ModeloCatalogueRecord(identifier="MODELO_303", name="IVA"))
        portal_repo = PortalRepository(session)
        created = portal_repo.upsert(
            PortalRecord(
                identifier="SEDE_ROOT",
                base_url=aeat_url("sede", "/").rstrip("/"),
                auth_method=PortalAuthMethod.CERTIFICATE,
                modelo_id=modelo.id,
                label="Sede electrónica",
            ),
        )
        assert created.auth_method is PortalAuthMethod.CERTIFICATE
        assert created.id is not None
        assert portal_repo.get(created.id).auth_method is PortalAuthMethod.CERTIFICATE


def test_corpus_artifact_repository_round_trip(tmp_path: Path) -> None:
    """:class:`CorpusArtifactRepository` persists and reads artifacts with FK integrity."""
    with _engine(tmp_path) as engine, session_scope(engine) as session:
        modelo = ModeloRepository(session).upsert(
            ModeloCatalogueRecord(identifier="MODELO_130", name="Pagos fraccionados"),
        )
        assert modelo.id is not None
        repo = CorpusArtifactRepository(session)
        created = repo.upsert(
            CorpusArtifactRecord(
                year=2024,
                modelo_id=modelo.id,
                file_path="corpus/2024/modelos/130/modelo-130-2024.pdf",
                sha256="a" * 64,
                source_url=sede_pdf_url(PDF_MODELO_130_2024_PATH_FIXTURE),
                fetched_at=datetime(2026, 4, 12, tzinfo=UTC),
            ),
        )
        assert created.id is not None
        listed = repo.list_all()
        assert len(listed) == 1
        assert listed[0].id == created.id
        assert listed[0].sha256 == created.sha256
        assert listed[0].modelo_id == modelo.id
