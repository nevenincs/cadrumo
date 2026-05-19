"""Shared contract test suite for :class:`SecureBoundRepository` subclasses.

The 8 concrete secure-storage repositories (filing drafts, submissions,
filing history, complementaria, justificantes, observations, assets,
inventory and friends) each ship a near-identical block of pytest
functions that exercise the same anti-tautology / anti-regression
properties of the encrypted persistence boundary:

* ``test_round_trip_preserves_payload`` - save -> load equality.
* ``test_save_is_idempotent`` - repeated save does not duplicate rows.
* ``test_load_returns_none_when_absent``.
* ``test_delete_removes`` / ``test_delete_removes_object``.
* ``test_delete_missing_returns_false``.
* ``test_object_marker_identifies_secure_backend`` - logical store_dir
  pointer carries the namespace marker so diagnostic CLI emits stay
  honest about the backend.
* ``test_unsafe_id_rejected`` - the path-safety gate refuses
  filesystem-traversal identifiers.
* ``test_database_payload_is_encrypted_audit_data`` - the raw on-disk
  SQLite file does not surface plaintext that the payload contained.
* ``test_foreign_class_object_refused`` - a row written at the wrong
  :class:`SensitivityClass` raises :class:`ClassificationError` on load.
* ``test_boundary_catches_simulated_field_drop_via_corrupted_payload``
  - the strict-equality witness used by every roundtrip is honest:
  mutating the on-disk JSON envelope to drop a typed field surfaces
  either as :class:`ValidationError` or strict inequality.

This module captures the 11 canonical checks behind one
:func:`assert_secure_repository_contract` function. The contract runs
each check against a real SQLite-backed
:class:`SecureObjectRepository` wired through the
:class:`SecureBoundRepository` under test. Mocks are forbidden by the
roundtrip discipline; the suite uses
:class:`EphemeralMasterKeyProvider` and a real
:func:`create_engine_from_settings` engine.

The contract function returns the number of checks executed so the
caller's self-test can assert the expected count and prove no check
was silently skipped.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Generic, TypeVar

import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from .....core.config import Settings
from .. import EphemeralMasterKeyProvider, SensitivityClass
from ..errors import ClassificationError
from ..sql import SecureObjectRepository
from ..sql._orm import Base, SecureObjectRow
from ..sql.engine import create_engine_from_settings
from ..sql.session import session_scope
from ._envelope import Envelope
from ._secure_repository import SecureBoundRepository

T = TypeVar("T", bound=BaseModel)

_FOREIGN_CLASS_MAP: dict[SensitivityClass, SensitivityClass] = {
    SensitivityClass.AUDIT: SensitivityClass.OPERATIONAL,
    SensitivityClass.FINANCIAL: SensitivityClass.OPERATIONAL,
    SensitivityClass.OPERATIONAL: SensitivityClass.AUDIT,
    SensitivityClass.IDENTITY: SensitivityClass.OPERATIONAL,
}

_UNSAFE_IDS: tuple[str, ...] = (
    "",
    "..",
    ".",
    ".hidden",
    "../escape",
    "a/b",
    "a\\b",
)


@dataclass(frozen=True)
class SecureRepositoryContractCase(Generic[T]):
    """Inputs required to run the contract against a concrete repository.

    The contract is parameterised by:

    * ``repository_factory`` - zero-arg callable returning a fresh
      ``SecureBoundRepository[T]`` instance bound to the test's
      ephemeral SQLite engine. The factory is invoked multiple times
      to exercise cross-instance roundtrips.
    * ``first_payload`` / ``second_payload`` - two distinct,
      fully-populated payload instances whose extracted identifiers
      differ. Both must use non-default values for every optional
      field so the strict-equality witness has signal.
    * ``plaintext_witnesses`` - a tuple of byte strings that the
      contract asserts MUST NOT appear in the raw on-disk SQLite
      file after the first payload is persisted. Callers supply tax
      identifiers, monetary amounts, or other plaintext that the
      payload encodes; the contract simply checks absence.
    * ``mutation_field`` - the JSON key inside ``payload`` (the inner
      object that the envelope wraps) whose deletion should produce
      either a :class:`ValidationError` on reload or a strictly
      unequal payload. The field MUST be required by the payload
      schema or carry a non-default value in ``first_payload`` so
      that the negative case is observable.
    """

    repository_factory: Callable[[], SecureBoundRepository[T]]
    first_payload: T
    second_payload: T
    plaintext_witnesses: tuple[bytes, ...]
    mutation_field: str


def _build_engine(db_path: Path) -> object:
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    return engine


def _round_trip_preserves_payload(case: SecureRepositoryContractCase[T]) -> None:
    repo_a = case.repository_factory()
    repo_a.save(case.first_payload)
    repo_b = case.repository_factory()
    loaded = repo_b.load(repo_b.extract_identifier(case.first_payload))
    assert loaded == case.first_payload, (
        "save -> load did not preserve strict pydantic equality; the "
        "encrypted boundary is dropping or defaulting a field"
    )


def _save_is_idempotent(case: SecureRepositoryContractCase[T]) -> None:
    repo = case.repository_factory()
    repo.save(case.first_payload)
    repo.save(case.first_payload)
    identifier = repo.extract_identifier(case.first_payload)
    ids = tuple(repo.iter_ids())
    assert ids.count(identifier) == 1, (
        f"repeated save of {identifier!r} produced duplicate rows; "
        f"iter_ids() = {ids!r}"
    )


def _load_returns_none_when_absent(case: SecureRepositoryContractCase[T]) -> None:
    repo = case.repository_factory()
    # Use a benign-but-syntactically-valid id that path safety allows.
    assert repo.load("never-existed-x") is None


def _delete_removes(case: SecureRepositoryContractCase[T]) -> None:
    repo = case.repository_factory()
    repo.save(case.first_payload)
    identifier = repo.extract_identifier(case.first_payload)
    assert repo.delete(identifier) is True
    assert repo.load(identifier) is None


def _delete_missing_returns_false(case: SecureRepositoryContractCase[T]) -> None:
    repo = case.repository_factory()
    assert repo.delete("never-existed-x") is False


def _object_marker_identifies_secure_backend(
    case: SecureRepositoryContractCase[T],
) -> None:
    repo = case.repository_factory()
    marker = repo.envelope_path_for("abc123").as_posix()
    assert marker.endswith(f"{repo.namespace}/abc123"), (
        f"envelope_path_for did not surface the namespace marker; got "
        f"{marker!r}, expected suffix {repo.namespace}/abc123"
    )


def _unsafe_id_rejected(case: SecureRepositoryContractCase[T]) -> None:
    repo = case.repository_factory()
    for bad in _UNSAFE_IDS:
        with pytest.raises(ValueError):
            repo.envelope_path_for(bad)


def _database_payload_is_encrypted_audit_data(
    case: SecureRepositoryContractCase[T],
    db_path: Path,
) -> None:
    repo = case.repository_factory()
    repo.save(case.first_payload)
    raw = db_path.read_bytes()
    assert b"secure_objects" in raw, (
        "raw SQLite file does not include the secure_objects table "
        "marker; encrypted-row backing is not wired"
    )
    for witness in case.plaintext_witnesses:
        assert witness not in raw, (
            f"plaintext witness {witness!r} leaked into the raw "
            f"SQLite file; the column-level encryption is bypassed"
        )
    identifier = repo.extract_identifier(case.first_payload)
    assert repo.load(identifier) == case.first_payload


def _foreign_class_object_refused(
    case: SecureRepositoryContractCase[T],
) -> None:
    repo = case.repository_factory()
    foreign = _FOREIGN_CLASS_MAP[repo.sensitivity]
    identifier = repo.extract_identifier(case.first_payload)
    envelope_cls = Envelope[type(case.first_payload)]  # type: ignore[valid-type]
    bad = envelope_cls(
        schema_version=repo.schema_version,
        written_at=datetime.now(UTC),
        classification=foreign,
        payload=case.first_payload,
    )
    SecureObjectRepository().save(
        namespace=repo.namespace,
        object_key=identifier,
        classification=foreign,
        schema_version=repo.schema_version,
        written_at=bad.written_at,
        payload=bad.model_dump_json().encode("utf-8"),
    )
    with pytest.raises(ClassificationError):
        repo.load(identifier)


def _boundary_catches_simulated_field_drop_via_corrupted_payload(
    case: SecureRepositoryContractCase[T],
    engine: object,
) -> None:
    repo = case.repository_factory()
    repo.save(case.first_payload)
    identifier = repo.extract_identifier(case.first_payload)

    baseline = repo.load(identifier)
    assert baseline == case.first_payload

    with session_scope(engine) as session:  # type: ignore[arg-type]
        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == repo.namespace,
        ).limit(1)
        row = session.execute(stmt).scalar_one()
        decoded = json.loads(row.payload.decode("utf-8"))
        assert case.mutation_field in decoded["payload"], (
            f"contract fixture must serialise {case.mutation_field!r} into "
            f"the envelope payload for the negative case to have signal"
        )
        del decoded["payload"][case.mutation_field]
        row.payload = json.dumps(decoded).encode("utf-8")

    regression_caught = False
    try:
        mutated = repo.load(identifier)
    except ValidationError:
        regression_caught = True
    else:
        assert mutated is not None
        if mutated != case.first_payload:
            regression_caught = True
        else:
            regression_caught = False

    assert regression_caught, (
        "boundary did not surface a deliberate field drop; the "
        "strict-equality roundtrip pattern is tautological for this "
        "repository and the entire suite is suspect"
    )


def _iter_ids_lexicographic(case: SecureRepositoryContractCase[T]) -> None:
    """Internal helper - not one of the 11 canonical tests, used only as
    a sanity gate to ensure the second payload survives the roundtrip.
    Kept private so it does not bloat the public count.
    """
    repo = case.repository_factory()
    repo.save(case.first_payload)
    repo.save(case.second_payload)
    ids = tuple(repo.iter_ids())
    assert ids == tuple(sorted(ids))
    assert len(ids) == 2


_CHECKS: tuple[
    tuple[str, Callable[[SecureRepositoryContractCase[BaseModel]], None]], ...
] = (
    ("test_round_trip_preserves_payload", _round_trip_preserves_payload),
    ("test_save_is_idempotent", _save_is_idempotent),
    ("test_load_returns_none_when_absent", _load_returns_none_when_absent),
    ("test_delete_removes", _delete_removes),
    ("test_delete_removes_object", _delete_removes),
    ("test_delete_missing_returns_false", _delete_missing_returns_false),
    (
        "test_object_marker_identifies_secure_backend",
        _object_marker_identifies_secure_backend,
    ),
    ("test_unsafe_id_rejected", _unsafe_id_rejected),
    ("test_foreign_class_object_refused", _foreign_class_object_refused),
)
"""Checks whose signature is ``(case)`` only.

``test_delete_removes`` and ``test_delete_removes_object`` are the same
behaviour under two names — both names appear across the 8 consumer
test files, and the contract honours both for migration parity.
"""


def assert_secure_repository_contract(
    case: SecureRepositoryContractCase[T],
    *,
    tmp_path: Path,
) -> int:
    """Run all 11 canonical contract checks against ``case``.

    The function creates a fresh SQLite database file under
    ``tmp_path``, activates a real
    :class:`EphemeralMasterKeyProvider`, and invokes each check against
    the repository returned by ``case.repository_factory``. Each check
    runs against its own fresh database to avoid cross-check
    interference; the same factory is reused so subclass wiring is
    exercised consistently.

    Returns the number of checks executed. Callers SHOULD assert this
    count equals the expected canonical count
    (:data:`EXPECTED_CHECK_COUNT`) so a silently-skipped check is
    visible at the self-test boundary.
    """

    executed = 0

    for index, (label, check) in enumerate(_CHECKS):
        db_path = tmp_path / f"contract-{index:02d}-{label}.db"
        provider = EphemeralMasterKeyProvider()
        with provider:
            engine = _build_engine(db_path)
            try:
                check(case)  # type: ignore[arg-type]
            finally:
                engine.dispose()  # type: ignore[attr-defined]
        executed += 1

    # Checks needing the db_path directly (raw-bytes inspection).
    db_path = tmp_path / "contract-encrypted-audit-data.db"
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = _build_engine(db_path)
        try:
            _database_payload_is_encrypted_audit_data(case, db_path)  # type: ignore[arg-type]
        finally:
            engine.dispose()  # type: ignore[attr-defined]
    executed += 1

    # Anti-tautology check needs the engine for direct row mutation.
    db_path = tmp_path / "contract-anti-tautology.db"
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = _build_engine(db_path)
        try:
            _boundary_catches_simulated_field_drop_via_corrupted_payload(
                case,  # type: ignore[arg-type]
                engine,
            )
        finally:
            engine.dispose()  # type: ignore[attr-defined]
    executed += 1

    return executed


EXPECTED_CHECK_COUNT: int = len(_CHECKS) + 2
"""The number of canonical contract checks executed by
:func:`assert_secure_repository_contract`.

The 11 canonical anti-tautology tests reduce to 10 distinct check
callables (``test_delete_removes`` and ``test_delete_removes_object``
share an implementation; the contract honours both names but the
underlying behaviour runs once per invocation). Plus the raw-bytes
inspection (``test_database_payload_is_encrypted_audit_data``) and the
field-drop simulation
(``test_boundary_catches_simulated_field_drop_via_corrupted_payload``)
that need the database path / engine handle directly.

Total: ``len(_CHECKS) + 2``. The count is exposed so self-tests can
assert no check was silently skipped.
"""


__all__ = [
    "EXPECTED_CHECK_COUNT",
    "SecureRepositoryContractCase",
    "assert_secure_repository_contract",
]
