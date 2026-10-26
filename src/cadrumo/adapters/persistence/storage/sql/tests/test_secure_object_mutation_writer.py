"""Real encrypted SQLite writes retain preparation, CAS and complete commit fences."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Connection, event

from ......core.classification.policies import SensitivityClass
from ......core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID, SecureObjectWrite
from ...errors import SecureObjectRevisionConflictError
from ...tests.ephemeral_bucket_session import EphemeralBucketSession
from .. import _secure_object_writes as writes_module
from ..secure_object_records import SecureObjectRevisionAssertion
from ..secure_objects import SecureObjectRepository
from ._secure_objects_support import _repo_at

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]
_NAMESPACE = "cadrumo.quickfile.writer.test"
_INSTANT = datetime(2026, 10, 1, 11, tzinfo=UTC)


def _write(key: str, *, expected: str | None = None) -> SecureObjectWrite:
    return SecureObjectWrite(
        namespace=_NAMESPACE,
        object_key=key,
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=_INSTANT,
        payload=b"synthetic confidential bytes",
        expected_revision_id=expected,
    )


def test_encryption_precedes_admission_and_sql_commit_finishes_inside_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = False
    commits: list[bool] = []
    encrypted: list[bytes] = []
    original_encrypt = writes_module.encrypt_secure_object_payload

    def encrypt(payload: bytes, *, associated_data: bytes) -> bytes:
        assert not active, "encryption and AAD preparation must precede the short writer fence"
        encrypted.append(payload)
        return original_encrypt(payload, associated_data=associated_data)

    def admitted(write: Callable[[], None]) -> None:
        nonlocal active
        active = True
        try:
            write()
            assert commits == [True], "the actual database commit must finish before releasing admission"
        finally:
            active = False

    def committed(_connection: Connection) -> None:
        commits.append(active)

    monkeypatch.setattr(writes_module, "encrypt_secure_object_payload", encrypt)
    with EphemeralBucketSession(), _repo_at(tmp_path / "prepared.db") as base:
        repository = SecureObjectRepository(engine=base.engine, mutation_writer=admitted)
        event.listen(base.engine, "commit", committed)
        try:
            repository.save_many((_write("prepared"),))
        finally:
            event.remove(base.engine, "commit", committed)
        assert base.exists(_NAMESPACE, "prepared")
        record = base.load(
            namespace=_NAMESPACE,
            object_key="prepared",
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=1,
        )
        assert record is not None and record.payload == encrypted[0]
    assert commits == [True] and len(encrypted) == 1 and not active


def test_assertions_and_empty_batches_never_request_mutation_admission(tmp_path: Path) -> None:
    def forbidden(_write: Callable[[], None]) -> None:
        raise AssertionError("assertion-only or empty work cannot confirm a mutation")

    with EphemeralBucketSession(), _repo_at(tmp_path / "assertions.db") as base:
        base.save_many((_write("source"),))
        source = base.load(
            namespace=_NAMESPACE,
            object_key="source",
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=1,
        )
        assert source is not None
        repository = SecureObjectRepository(engine=base.engine, mutation_writer=forbidden)
        repository.apply_batch(writes=(), deletions=())
        repository.apply_batch(
            writes=(),
            deletions=(),
            assertions=(
                SecureObjectRevisionAssertion(
                    namespace=_NAMESPACE, object_key="source", expected_revision_id=source.revision_id
                ),
            ),
        )
        assert base.exists(_NAMESPACE, "source")


def test_rejected_batch_cas_rolls_back_sibling_rows_before_any_confirmation(tmp_path: Path) -> None:
    attempts = 0
    confirmed = 0

    def admitted(write: Callable[[], None]) -> None:
        nonlocal attempts, confirmed
        attempts += 1
        write()
        confirmed += 1

    with EphemeralBucketSession(), _repo_at(tmp_path / "cas.db") as base:
        base.save_many((_write("occupied"),))
        repository = SecureObjectRepository(engine=base.engine, mutation_writer=admitted)
        with pytest.raises(SecureObjectRevisionConflictError):
            repository.save_many(
                (
                    _write("sibling", expected=ABSENT_SECURE_OBJECT_REVISION_ID),
                    _write("occupied", expected=ABSENT_SECURE_OBJECT_REVISION_ID),
                )
            )
        assert not base.exists(_NAMESPACE, "sibling") and base.exists(_NAMESPACE, "occupied")
    assert attempts == 1 and confirmed == 0
