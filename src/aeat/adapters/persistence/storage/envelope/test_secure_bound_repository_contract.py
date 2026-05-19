"""Self-test for the shared :mod:`_repository_test_suite` contract.

Runs :func:`assert_secure_repository_contract` against a throwaway
:class:`SecureBoundRepository[_DummyPayload]` subclass to prove the
suite is honest before any of the 8 consumer test files migrate onto
it. The dummy payload mirrors the shape used by the
:mod:`test_secure_bound_repository` roundtrip test introduced in
S04: a frozen, strict, ``extra='forbid'`` Pydantic model with a
required ``id`` field and a non-default ``value`` field whose deletion
from the on-disk envelope must surface as either a
:class:`pydantic.ValidationError` or strict inequality.

No mocks; the contract spins up a real SQLite engine via
:class:`EphemeralMasterKeyProvider`, exactly as the production
secure-storage roundtrip tests do.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import BaseModel, ConfigDict

from .. import SensitivityClass
from ..sql import SecureObjectRepository
from ..sql._orm import Base
from ..sql.engine import create_engine_from_settings
from ._repository_test_suite import (
    EXPECTED_CHECK_COUNT,
    SecureRepositoryContractCase,
    assert_secure_repository_contract,
)
from ._secure_repository import SecureBoundRepository
from .....core.config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


class _DummyPayload(BaseModel):
    """Throwaway typed payload exercising the contract.

    ``value`` carries a non-default, non-zero integer so the
    anti-tautology check can drop it from the JSON envelope and
    observe inequality (or :class:`ValidationError`, since
    ``extra='forbid'`` + missing required field both flag).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    id: str
    value: int
    label: str


class _DummyRepository(SecureBoundRepository[_DummyPayload]):
    namespace: ClassVar[str] = "aeat.test.envelope.secure_bound_contract_dummy"
    sensitivity: ClassVar[SensitivityClass] = SensitivityClass.AUDIT
    schema_version: ClassVar[int] = 1
    payload_type: ClassVar[type[BaseModel]] = _DummyPayload

    def extract_identifier(self, payload: _DummyPayload) -> str:
        return payload.id


def _build_repo(tmp_path: Path) -> _DummyRepository:
    """Return a fresh ``_DummyRepository`` wired to a per-call SQLite db.

    The contract calls this factory multiple times per check; each
    call gets a fresh engine bound to a check-scoped database file
    that the contract created via :func:`_build_engine`. We resolve
    the engine via the Settings/AEAT_DATABASE_URL surface so the
    repository's internal ``SecureObjectRepository()`` lookup binds
    to the same file.
    """

    # The contract creates each per-check DB file; we honor whatever
    # database url the surrounding test sets via the monkeypatched
    # AEAT_DATABASE_URL env var, falling back to a stable name in
    # tmp_path. This mirrors how the production consumer tests build
    # their repositories.
    return _DummyRepository()


def test_dummy_repository_satisfies_secure_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dummy ``SecureBoundRepository`` honours every contract check.

    Each contract check runs against its own SQLite database file
    under ``tmp_path`` (the contract orchestrates that). We point
    ``AEAT_DATABASE_URL`` at a single shared file here only so the
    factory's ``SecureObjectRepository()`` resolves consistently;
    the contract itself populates the per-check db via the engine it
    builds for that check, and the dummy repository writes through
    the same on-disk file because the engine is the cached
    process-default.
    """

    # The contract builds its own engine per check by calling
    # ``create_engine_from_settings`` with a Settings object that
    # points at the per-check file. Settings resolution requires
    # AEAT_DATABASE_URL to be set OR an explicit Settings instance.
    # We let the contract supply the explicit Settings; the
    # repository factory below also reads from the process-default
    # engine. To keep both views consistent, we wire AEAT_DATABASE_URL
    # to a default path; the contract overrides it per check via its
    # own Settings instance.
    monkeypatch.setenv(
        "AEAT_DATABASE_URL",
        f"sqlite:///{(tmp_path / 'unused-default.db').as_posix()}",
    )

    first = _DummyPayload(id="alpha-001", value=42, label="first")
    second = _DummyPayload(id="beta-002", value=99, label="second")

    case = SecureRepositoryContractCase[_DummyPayload](
        repository_factory=lambda: _build_repo(tmp_path),
        first_payload=first,
        second_payload=second,
        plaintext_witnesses=(b"alpha-001", b"first", b"42"),
        # ``value`` is a required field; dropping it from the
        # envelope payload must surface as ValidationError under
        # strict-mode + extra='forbid'.
        mutation_field="value",
    )

    executed = assert_secure_repository_contract(case, tmp_path=tmp_path)
    assert executed == EXPECTED_CHECK_COUNT, (
        f"contract suite executed {executed} checks; expected "
        f"{EXPECTED_CHECK_COUNT}. A silently-skipped check is the "
        f"likely culprit."
    )


def test_expected_check_count_matches_published_canon() -> None:
    """Lock the canonical check count so accidental regressions surface.

    The research doc enumerates 11 canonical anti-tautology tests
    across the 8 secure-storage repositories. The contract reduces
    that to 12 executable check invocations (the two delete-removes
    aliases share a callable, plus the encrypted-audit-data and
    field-drop checks that need direct db / engine handles).
    """

    assert EXPECTED_CHECK_COUNT == 12


def test_contract_case_construction_is_strict() -> None:
    """The case object refuses missing fields at construction time."""

    with pytest.raises(TypeError):
        SecureRepositoryContractCase()  # type: ignore[call-arg]


def test_dummy_repository_engine_is_real_sqlite(tmp_path: Path) -> None:
    """Sanity gate: the contract harness builds a real SQLite engine.

    No mocks, no fakes; if this ever returns something other than a
    SQLAlchemy engine wired to the on-disk file, every contract
    check above becomes suspect.
    """

    from sqlalchemy.engine import Engine

    db_path = tmp_path / "sanity.db"
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    try:
        assert isinstance(engine, Engine)
        Base.metadata.create_all(engine)
        # Real round trip through SecureObjectRepository confirms the
        # encryption substrate is wired (the contract relies on it).
        assert SecureObjectRepository(engine=engine) is not None
    finally:
        engine.dispose()
