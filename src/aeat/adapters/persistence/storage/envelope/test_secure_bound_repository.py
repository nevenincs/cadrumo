"""Roundtrip coverage for the generic :class:`SecureBoundRepository`.

Exercises save -> load -> iter -> delete against a real SQLite-backed
:class:`SecureObjectRepository` with a real
:class:`EphemeralMasterKeyProvider`. No mocks; this is the
anti-tautology, anti-regression gate for the new base class.

A throwaway ``_DummyPayload`` Pydantic model and a throwaway concrete
:class:`SecureBoundRepository` subclass live inside this module —
production migrations of the 8 concrete repositories ship under
subsequent steps.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine

from .....core.config import Settings, override_settings
from .. import EphemeralMasterKeyProvider, SensitivityClass
from ..errors import EnvelopeVersionError, StorageValidationError
from ..sql import SecureObjectRepository
from ..sql._orm import Base
from ..sql.engine import create_engine_from_settings
from ._envelope import Envelope
from ._secure_repository import SecureBoundRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


class _DummyPayload(BaseModel):
    """Throwaway typed payload exercised by the base-class roundtrip test."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    id: str
    value: int


class _DummyRepository(SecureBoundRepository[_DummyPayload]):
    """Concrete subclass wiring the four class-level descriptors."""

    namespace: ClassVar[str] = "aeat.test.envelope.secure_bound_dummy"
    sensitivity: ClassVar[SensitivityClass] = SensitivityClass.AUDIT
    schema_version: ClassVar[int] = 1
    payload_type: ClassVar[type[BaseModel]] = _DummyPayload

    def extract_identifier(self, payload: _DummyPayload) -> str:
        return payload.id


def _bound_repo_with_engine(tmp_path: Path) -> tuple[_DummyRepository, Engine]:
    """Build an isolated SQLite engine + repository against ``tmp_path``."""

    db_path = tmp_path / "secure-bound-roundtrip.db"
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    objects = SecureObjectRepository(engine=engine)
    repo = _DummyRepository(objects=objects)
    return repo, engine


def test_secure_bound_repository_save_load_iter_delete_roundtrip(
    tmp_path: Path,
) -> None:
    """Full CRUD cycle survives the encrypted SQL boundary intact."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        repo, engine = _bound_repo_with_engine(tmp_path)
        try:
            first = _DummyPayload(id="alpha", value=42)
            second = _DummyPayload(id="beta", value=99)

            repo.save(first)
            repo.save(second)

            loaded = repo.load("alpha")
            assert loaded == first
            assert loaded is not None and loaded.value == 42

            # Lexicographic id ordering is part of the contract.
            assert tuple(repo.iter_ids()) == ("alpha", "beta")
            assert tuple(repo.iter_records()) == (first, second)

            assert repo.delete("alpha") is True
            assert repo.delete("alpha") is False
            assert repo.load("alpha") is None
            assert tuple(repo.iter_ids()) == ("beta",)
        finally:
            engine.dispose()


def test_secure_bound_repository_missing_returns_none(tmp_path: Path) -> None:
    """``load`` for an unknown identifier returns ``None``, never raises."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        repo, engine = _bound_repo_with_engine(tmp_path)
        try:
            assert repo.load("nonexistent") is None
        finally:
            engine.dispose()


def test_secure_bound_repository_default_refuses_active_profile_without_session(
    tmp_path: Path,
) -> None:
    """Default construction does not fall back when an active profile is selected."""

    with (
        override_settings(
            aeat_local_storage_root=tmp_path,
            aeat_active_profile="secure-bound-bucket",
        ),
        pytest.raises(StorageValidationError, match="no active bucket session"),
    ):
        _DummyRepository()


def test_secure_bound_repository_rejects_future_schema_version(
    tmp_path: Path,
) -> None:
    """A row written at a future schema version trips the version gate.

    The bound repository declares ``schema_version=1``; we plant an
    envelope serialised at version ``2`` directly through
    :class:`SecureObjectRepository` and confirm the bound load surface
    raises :class:`EnvelopeVersionError` rather than returning the
    payload. This guards against a silent forward-compatibility drift
    in the base class load path.
    """

    from datetime import UTC, datetime

    provider = EphemeralMasterKeyProvider()
    with provider:
        repo, engine = _bound_repo_with_engine(tmp_path)
        try:
            future_payload = _DummyPayload(id="future", value=7)
            future_envelope = Envelope[_DummyPayload](
                schema_version=2,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.AUDIT,
                payload=future_payload,
            )
            # Write directly through the underlying object store so the
            # row carries schema_version=2 even though the bound repo
            # declares max=1.
            repo._objects.save(
                namespace=_DummyRepository.namespace,
                object_key="future",
                classification=SensitivityClass.AUDIT,
                schema_version=2,
                written_at=future_envelope.written_at,
                payload=future_envelope.model_dump_json().encode("utf-8"),
            )

            with pytest.raises(EnvelopeVersionError):
                repo.load("future")
        finally:
            engine.dispose()
