"""Self-test for the shared repository contract support.

Runs :func:`assert_secure_repository_contract` against a throwaway
:class:`SecureBoundRepository[_ContractPayload]` subclass to prove the
suite is honest before any of the 8 consumer test files migrate onto
it. The contract payload mirrors the shape used by the
:mod:`test_secure_bound_repository` roundtrip test introduced in
contract: a frozen, strict, ``extra='forbid'`` Pydantic model with a
required ``id`` field plus two further required fields whose
deletion from the on-disk envelope must surface as either a
:class:`pydantic.ValidationError` or strict inequality.

No mocks; the contract spins up a real SQLite engine via
:class:`EphemeralMasterKeyProvider`, exactly as the production
secure-storage roundtrip tests do.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, override

import pytest
from pydantic import BaseModel, ConfigDict

from ......core.classification.policies import SensitivityClass
from ......core.config import Settings
from ...sql import Base, SecureObjectRepository
from ...sql.engine import create_engine_from_settings
from .._secure_repository import SecureBoundRepository
from ._repository_contract_support import (
    EXPECTED_CHECK_COUNT,
    SecureRepositoryContractCase,
    assert_secure_repository_contract,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


class _ContractPayload(BaseModel):
    """Throwaway typed payload exercising the contract.

    Three required fields keep the strict-equality witness honest:
    dropping any one of them from the envelope payload must surface
    as inequality (or :class:`ValidationError` under strict mode +
    ``extra='forbid'``).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    id: str
    value: int
    label: str


class _ContractRepository(SecureBoundRepository[_ContractPayload]):
    namespace: ClassVar[str] = "cadrumo-test.envelope.secure_bound_contract"
    sensitivity: ClassVar[SensitivityClass] = SensitivityClass.AUDIT
    schema_version: ClassVar[int] = 1
    payload_type: ClassVar[type[BaseModel]] = _ContractPayload

    @override
    def extract_identifier(self, payload: _ContractPayload) -> str:
        return payload.id


def test_contract_repository_satisfies_secure_contract(
    tmp_path: Path,
) -> None:
    """The contract ``SecureBoundRepository`` honours every contract check."""

    first = _ContractPayload(id="alpha-001", value=4242, label="firstwitness")
    second = _ContractPayload(id="beta-002", value=9999, label="secondwitness")

    case = SecureRepositoryContractCase[_ContractPayload](
        repository_factory=_ContractRepository,
        first_payload=first,
        second_payload=second,
        # All three string witnesses appear plainly in the original
        # payload; if any leaked into the raw SQLite file, the
        # column-level encryption substrate is bypassed.
        plaintext_witnesses=(b"alpha-001", b"firstwitness", b"4242"),
        mutation_field="value",
    )

    executed = assert_secure_repository_contract(
        case,
        tmp_path=tmp_path,
    )
    assert executed == EXPECTED_CHECK_COUNT, (
        f"contract suite executed {executed} checks; expected "
        f"{EXPECTED_CHECK_COUNT}. A silently-skipped check is the "
        f"likely culprit."
    )


def test_expected_check_count_matches_published_canon() -> None:
    """Lock the canonical check count so accidental regressions surface.

    The research doc enumerates 11 canonical anti-tautology tests
    across the 8 secure-storage repositories. The two delete-removes
    aliases (``test_delete_removes`` and ``test_delete_removes_object``)
    share a callable but are invoked under both names, plus the
    encrypted-audit-data and field-drop checks need direct db /
    engine handles. Total: 11 invocations.
    """

    assert EXPECTED_CHECK_COUNT == 11


def test_contract_repository_engine_is_real_sqlite(tmp_path: Path) -> None:
    """Sanity gate: the contract harness builds a real SQLite engine.

    No mocks, no fakes; if this ever returns something other than a
    SQLAlchemy engine wired to the on-disk file, every contract
    check above becomes suspect.
    """

    from sqlalchemy.engine import Engine

    db_path = tmp_path / "sanity.db"
    engine = create_engine_from_settings(
        Settings(cadrumo_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    try:
        assert isinstance(engine, Engine)
        Base.metadata.create_all(engine)
        assert SecureObjectRepository(engine=engine) is not None
    finally:
        engine.dispose()
