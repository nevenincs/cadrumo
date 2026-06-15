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
from typing import ClassVar, override

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, text

from ......core.config import Settings, override_settings
from ... import EphemeralMasterKeyProvider, SensitivityClass
from ...errors import EnvelopeVersionError, SecureObjectUnreadableError, StorageValidationError
from ...sql import SecureObjectRepository
from ...sql._orm import Base
from ...sql.engine import create_engine_from_settings
from ...sql.secure_objects import SecureObjectRecord, SecureObjectUnreadable
from ...sql.session import session_scope
from .._envelope import Envelope
from .._secure_repository import SecureBoundRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


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

    @override
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

            # Enumeration yields the full set in storage order (digest order),
            # not a sorted order: callers that need a specific order sort the
            # result. Compare order-independently (sort both sides by id).
            assert sorted(repo.iter_ids()) == ["alpha", "beta"]
            assert sorted(repo.iter_records(), key=lambda p: p.id) == [first, second]

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


def test_secure_bound_repository_iter_ids_fails_closed_on_unreadable_row(
    tmp_path: Path,
) -> None:
    """Bound repository enumeration must not return a readable subset."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        repo, engine = _bound_repo_with_engine(tmp_path)
        try:
            repo.save(_DummyPayload(id="alpha", value=42))
            repo.save(_DummyPayload(id="beta", value=99))
            with session_scope(engine) as session:
                session.execute(
                    text(
                        "UPDATE secure_objects SET payload = X'00' "
                        "WHERE id = ("
                        "SELECT MIN(id) FROM secure_objects WHERE namespace = :namespace"
                        ")",
                    ),
                    {"namespace": _DummyRepository.namespace},
                )

            with pytest.raises(SecureObjectUnreadableError):
                tuple(repo.iter_ids())
        finally:
            engine.dispose()


def test_secure_bound_repository_underlying_iterator_still_reports_partial_failures(
    tmp_path: Path,
) -> None:
    """The explicit diagnostic iterator remains available for repair-style callers."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        repo, engine = _bound_repo_with_engine(tmp_path)
        try:
            repo.save(_DummyPayload(id="alpha", value=42))
            repo.save(_DummyPayload(id="beta", value=99))
            with session_scope(engine) as session:
                session.execute(
                    text(
                        "UPDATE secure_objects SET payload = X'00' "
                        "WHERE id = ("
                        "SELECT MIN(id) FROM secure_objects WHERE namespace = :namespace"
                        ")",
                    ),
                    {"namespace": _DummyRepository.namespace},
                )

            outcomes = tuple(
                repo._objects.iter_records_with_failures(
                    _DummyRepository.namespace,
                    expected_class=_DummyRepository.sensitivity,
                    max_supported_version=_DummyRepository.schema_version,
                ),
            )

            assert len([item for item in outcomes if isinstance(item, SecureObjectRecord)]) == 1
            assert len([item for item in outcomes if isinstance(item, SecureObjectUnreadable)]) == 1
        finally:
            engine.dispose()


# ---------------------------------------------------------------------------
# contract: envelope payload type preservation across the generic boundary
# ---------------------------------------------------------------------------


def test_envelope_payload_type_is_preserved_across_generic_boundary(
    tmp_path: Path,
) -> None:
    """Payload type identity is preserved through the save -> load cycle.

    Asserts that the object returned by ``repo.load()`` is a real
    ``_DummyPayload`` instance (not a plain dict or BaseModel), confirming
    that ``_envelope_cls()`` produces a validating ``Envelope[_DummyPayload]``
    and that the cast at the load boundary is genuinely safe.
    """
    provider = EphemeralMasterKeyProvider()
    with provider:
        repo, engine = _bound_repo_with_engine(tmp_path)
        try:
            original = _DummyPayload(id="type-check", value=7)
            repo.save(original)
            loaded = repo.load("type-check")

            assert loaded is not None
            # Runtime type must be the concrete payload model, not a supertype.
            assert type(loaded) is _DummyPayload
            assert isinstance(loaded, _DummyPayload)
            # Field equality confirms Pydantic validated the JSON correctly.
            assert loaded == original
        finally:
            engine.dispose()


# ---------------------------------------------------------------------------
# contract: typed factory yields the correct envelope subtype per payload
# ---------------------------------------------------------------------------


def test_envelope_for_payload_type_returns_correct_parameterised_class() -> None:
    """``Envelope.for_payload_type`` returns a class that validates the payload.

    Asserts:
    - The returned class is a subclass/alias of ``Envelope``.
    - ``model_validate_json`` on the returned class accepts valid JSON.
    - ``model_validate_json`` rejects JSON whose payload does not match.
    """
    from datetime import UTC, datetime

    from pydantic import ValidationError

    env_cls = Envelope.for_payload_type(_DummyPayload)

    # The factory must return a class, not an instance.
    assert isinstance(env_cls, type)

    # A valid envelope round-trips cleanly.
    import json

    valid_json = json.dumps(
        {
            "schema_version": 1,
            "written_at": datetime.now(UTC).isoformat(),
            "classification": SensitivityClass.AUDIT.value,
            "payload": {"id": "x", "value": 3},
            "encryption": None,
        },
    )
    loaded = env_cls.model_validate_json(valid_json)
    assert isinstance(loaded.payload, _DummyPayload)
    assert loaded.payload.id == "x"

    # A payload with wrong field types must be rejected by Pydantic.
    bad_json = json.dumps(
        {
            "schema_version": 1,
            "written_at": datetime.now(UTC).isoformat(),
            "classification": SensitivityClass.AUDIT.value,
            "payload": {"id": "x", "value": "not-an-int"},
            "encryption": None,
        },
    )
    with pytest.raises(ValidationError):
        env_cls.model_validate_json(bad_json)


# ---------------------------------------------------------------------------
# contract: CI assertion that cast rationale markers are present in source
# ---------------------------------------------------------------------------


def test_cast_rationale_markers_present_in_secure_repository_source() -> None:
    """Assert that rationale-marker comments survive refactoring.

    Each ``cast()`` call in ``_secure_repository.py`` that cannot yet be
    eliminated must carry a CAST-RATIONALE-* marker. This test reads the
    source file and asserts the markers are present, acting as a CI gate
    that blocks silent removal of documented safety rationale.
    """
    import pathlib

    source = pathlib.Path(__file__).parent.parent / "_secure_repository.py"
    text = source.read_text(encoding="utf-8")

    required_markers = [
        "CAST-RATIONALE-SECURE-REPOSITORY-LOAD",
        "CAST-RATIONALE-SECURE-REPOSITORY-ITER",
        "CAST-RATIONALE-SECURE-REPOSITORY-ENVCLS",
    ]
    for marker in required_markers:
        assert marker in text, (
            f"Cast rationale marker {marker!r} is missing from {source}. Either restore the comment or remove the cast."
        )
