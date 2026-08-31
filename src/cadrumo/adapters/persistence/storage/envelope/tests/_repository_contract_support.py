"""Shared contract support for :class:`SecureBoundRepository` subclasses.

The 8 concrete secure-storage repositories (filing drafts, submissions,
filing history, complementaria, justificantes, observations, assets,
inventory and friends) each ship a near-identical block of pytest
functions that exercise the same anti-tautology / anti-regression
properties of the encrypted persistence boundary:

* ``test_round_trip_preserves_payload`` - save -> load equality across
  the :class:`Envelope` boundary.
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

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy import Engine, select

from ......core.classification.policies import SensitivityClass
from ......core.config import override_settings
from ......tests.master_key import EphemeralMasterKeyProvider
from ......tests.secure_sql import mutate_encrypted_secure_object_json
from ...errors import ClassificationError
from ...sql import Base, SecureObjectRow
from ...sql.engine import create_engine_from_settings, dispose_engine
from ..contract import Envelope
from ..secure_bound_repository import SecureBoundRepository

_FOREIGN_CLASS_MAP: dict[SensitivityClass, SensitivityClass] = {
    SensitivityClass.AUDIT: SensitivityClass.OPERATIONAL,
    SensitivityClass.FINANCIAL: SensitivityClass.OPERATIONAL,
    SensitivityClass.OPERATIONAL: SensitivityClass.AUDIT,
    SensitivityClass.IDENTITY: SensitivityClass.OPERATIONAL,
    SensitivityClass.SECRET: SensitivityClass.OPERATIONAL,
    SensitivityClass.SESSION: SensitivityClass.OPERATIONAL,
    SensitivityClass.CACHE: SensitivityClass.AUDIT,
    SensitivityClass.CORPUS: SensitivityClass.AUDIT,
    SensitivityClass.DIAGNOSTIC: SensitivityClass.AUDIT,
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
_FOREIGN_CLASS_WRITTEN_AT = datetime(2026, 5, 26, 18, 0, 0, tzinfo=UTC)


@dataclass(frozen=True)
class SecureRepositoryContractCase[T: BaseModel]:
    """Inputs required to run the contract against a concrete repository.

    The contract is parameterised by:

    * ``repository_factory`` - zero-arg callable returning a fresh
      ``SecureBoundRepository[T]`` instance. Invoked repeatedly so
      cross-instance roundtrips are exercised. The factory MUST
      route its underlying :class:`SecureObjectRepository` at the
      currently-active process-default engine (i.e. construct
      ``Concrete()`` rather than passing an explicit engine), because
      the contract harness rebinds ``CADRUMO_DATABASE_URL`` to a fresh
      SQLite file per check and disposes cached engines between
      checks.
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


@contextmanager
def _activated_engine(db_path: Path):
    """Repoint the process-default engine at ``db_path`` for one check.

    Disposes cached engines, binds the database and storage-root settings through
    the canonical ContextVar-backed settings surface, then yields a fresh engine
    whose schema is materialised against ``Base.metadata``.
    """
    dispose_engine()
    url = f"sqlite:///{db_path.as_posix()}"
    with override_settings(
        cadrumo_local_storage_root=db_path.parent / "storage-root",
        cadrumo_database_url=url,
    ) as settings:
        engine = create_engine_from_settings(settings)
        try:
            Base.metadata.create_all(engine)
            yield engine
        finally:
            engine.dispose()
            dispose_engine(settings)


def _round_trip_preserves_payload[T: BaseModel](
    case: SecureRepositoryContractCase[T],
) -> None:
    repo_a = case.repository_factory()
    repo_a.save(case.first_payload)
    repo_b = case.repository_factory()
    loaded = repo_b.load(repo_b.extract_identifier(case.first_payload))
    assert loaded == case.first_payload, (
        "save -> load did not preserve strict pydantic equality; the "
        "encrypted boundary is dropping or defaulting a field"
    )


def _save_is_idempotent[T: BaseModel](case: SecureRepositoryContractCase[T]) -> None:
    repo = case.repository_factory()
    repo.save(case.first_payload)
    repo.save(case.first_payload)
    identifier = repo.extract_identifier(case.first_payload)
    ids = tuple(repo.iter_ids())
    assert ids.count(identifier) == 1, f"repeated save of {identifier!r} produced duplicate rows; iter_ids() = {ids!r}"


def _load_returns_none_when_absent[T: BaseModel](
    case: SecureRepositoryContractCase[T],
) -> None:
    repo = case.repository_factory()
    assert repo.load("never-existed-x") is None


def _delete_removes[T: BaseModel](case: SecureRepositoryContractCase[T]) -> None:
    repo = case.repository_factory()
    repo.save(case.first_payload)
    identifier = repo.extract_identifier(case.first_payload)
    assert repo.delete(identifier) is True
    assert repo.load(identifier) is None


def _delete_missing_returns_false[T: BaseModel](
    case: SecureRepositoryContractCase[T],
) -> None:
    repo = case.repository_factory()
    assert repo.delete("never-existed-x") is False


def _object_marker_identifies_secure_backend[T: BaseModel](
    case: SecureRepositoryContractCase[T],
) -> None:
    repo = case.repository_factory()
    marker = repo.envelope_path_for("abc123").as_posix()
    assert marker.endswith(f"{repo.namespace}/abc123"), (
        f"envelope_path_for did not surface the namespace marker; got "
        f"{marker!r}, expected suffix {repo.namespace}/abc123"
    )


def _unsafe_id_rejected[T: BaseModel](case: SecureRepositoryContractCase[T]) -> None:
    repo = case.repository_factory()
    for bad in _UNSAFE_IDS:
        with pytest.raises(ValueError):
            repo.envelope_path_for(bad)


def _database_payload_is_encrypted_audit_data[T: BaseModel](
    case: SecureRepositoryContractCase[T],
    db_path: Path,
) -> None:
    from ......tests.secure_sql import read_db_at_rest_bytes

    repo = case.repository_factory()
    repo.save(case.first_payload)
    raw = read_db_at_rest_bytes(db_path)
    assert b"secure_objects" in raw, (
        "raw SQLite file does not include the secure_objects table marker; encrypted-row backing is not wired"
    )
    for witness in case.plaintext_witnesses:
        assert witness not in raw, (
            f"plaintext witness {witness!r} leaked into the raw SQLite file; the column-level encryption is bypassed"
        )
    identifier = repo.extract_identifier(case.first_payload)
    assert repo.load(identifier) == case.first_payload


def _foreign_class_object_refused[T: BaseModel](
    case: SecureRepositoryContractCase[T],
) -> None:
    repo = case.repository_factory()
    foreign = _FOREIGN_CLASS_MAP[repo.sensitivity]
    identifier = repo.extract_identifier(case.first_payload)
    payload_cls = type(case.first_payload)
    # CAST-RATIONALE-ENVELOPE-REPO-SUITE-CLASS-GETITEM: ``Envelope[T]`` is
    # parameterised via PEP-695 generic syntax; the subscription is a runtime
    # concrete-class build, but the type checker cannot narrow ``payload_cls``
    # to a static ``type[T]`` here, so the cast to ``Any`` is required to
    # call the resulting parameterised factory without a spurious type error.
    envelope_factory = cast(Any, Envelope.__class_getitem__(payload_cls))
    written_at = _FOREIGN_CLASS_WRITTEN_AT
    bad = envelope_factory(
        schema_version=repo.schema_version,
        written_at=written_at,
        classification=foreign,
        payload=case.first_payload,
    )
    try:
        repo._objects.save(
            namespace=repo.namespace,
            object_key=identifier,
            classification=foreign,
            schema_version=repo.schema_version,
            written_at=written_at,
            payload=bad.model_dump_json().encode("utf-8"),
        )
    except ClassificationError:
        return
    with pytest.raises(ClassificationError):
        repo.load(identifier)


def _boundary_catches_simulated_field_drop_via_corrupted_payload[T: BaseModel](
    case: SecureRepositoryContractCase[T],
    engine: Engine,
) -> None:
    repo = case.repository_factory()
    repo.save(case.first_payload)
    identifier = repo.extract_identifier(case.first_payload)

    baseline = repo.load(identifier)
    assert baseline == case.first_payload

    stmt = select(SecureObjectRow).where(SecureObjectRow.namespace == repo.namespace).limit(1)

    def mutate(decoded: dict[str, Any]) -> None:
        assert case.mutation_field in decoded["payload"], (
            f"contract fixture must serialise {case.mutation_field!r} into "
            f"the envelope payload for the negative case to have signal"
        )
        del decoded["payload"][case.mutation_field]

    mutate_encrypted_secure_object_json(engine, row_statement=stmt, mutate=mutate)

    regression_caught = False
    try:
        mutated = repo.load(identifier)
    except ValidationError:
        regression_caught = True
    else:
        if mutated is None or mutated != case.first_payload:
            regression_caught = True

    assert regression_caught, (
        "boundary did not surface a deliberate field drop; the "
        "strict-equality roundtrip pattern is tautological for this "
        "repository and the entire suite is suspect"
    )


_ParamCheck = Callable[..., None]
"""Each entry is one of the ``[T]``-generic check functions below, instantiated
at whatever ``T`` the caller's :class:`SecureRepositoryContractCase` carries.
A precise ``Callable[[SecureRepositoryContractCase[BaseModel]], None]`` cannot
hold a generic function without erasing it back to one concrete ``T``, which
is exactly the erasure :func:`assert_secure_repository_contract` already
performs at the call site (see its own cast rationale). Declaring the
parameter shape here would just repeat that erasure one level up; the ellipsis
states plainly that this table does not itself enforce it."""

_PARAM_CHECKS: tuple[tuple[str, _ParamCheck], ...] = (
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


def assert_secure_repository_contract[T: BaseModel](
    case: SecureRepositoryContractCase[T],
    *,
    tmp_path: Path,
) -> int:
    """Run all 11 canonical contract checks against ``case``.

    For each check the function:

      1. Disposes any cached process-default engine.
      2. Rebinds ``CADRUMO_DATABASE_URL`` and ``CADRUMO_LOCAL_STORAGE_ROOT``
         through ``override_settings`` to a fresh SQLite file under ``tmp_path``.
      3. Builds a real engine for that URL and materialises the ORM
         schema.
      4. Activates a real :class:`EphemeralMasterKeyProvider`.
      5. Invokes the check, which constructs the repository via
         ``case.repository_factory``; the repository's internal
         :class:`SecureObjectRepository` lookup resolves to the
         engine activated above.
      6. Disposes the engine.

    Returns the number of checks executed. Callers SHOULD assert this
    count equals :data:`EXPECTED_CHECK_COUNT` so a silently-skipped
    check is visible at the self-test boundary.
    """
    executed = 0

    # CAST-RATIONALE-ENVELOPE-REPO-SUITE-CONTRACT-ERASE: ``case`` is typed
    # as ``SecureRepositoryContractCase[T]`` where ``T`` is a bound TypeVar;
    # the type-erased ``BaseModel`` form is needed to satisfy the untyped
    # ``_PARAM_CHECKS`` dispatch table without widening every check signature.
    erased = cast(SecureRepositoryContractCase[BaseModel], case)
    for index, (label, check) in enumerate(_PARAM_CHECKS):
        db_path = tmp_path / f"contract-{index:02d}-{label}.db"
        provider = EphemeralMasterKeyProvider()
        with provider, _activated_engine(db_path):
            check(erased)
        executed += 1

    db_path = tmp_path / "contract-encrypted-audit-data.db"
    provider = EphemeralMasterKeyProvider()
    with provider, _activated_engine(db_path):
        _database_payload_is_encrypted_audit_data(erased, db_path)
    executed += 1

    db_path = tmp_path / "contract-anti-tautology.db"
    provider = EphemeralMasterKeyProvider()
    with provider, _activated_engine(db_path) as engine:
        _boundary_catches_simulated_field_drop_via_corrupted_payload(
            erased,
            engine,
        )
    executed += 1

    return executed


EXPECTED_CHECK_COUNT: int = len(_PARAM_CHECKS) + 2
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

Total: ``len(_PARAM_CHECKS) + 2``.
"""


__all__ = [
    "EXPECTED_CHECK_COUNT",
    "SecureRepositoryContractCase",
    "assert_secure_repository_contract",
]
