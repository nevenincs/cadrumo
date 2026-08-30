"""Atomic upsert+delete batch + diff-scan contract for SecureObjectRepository.

``apply_batch`` is the primitive that lets a namespace be persisted as one
secure-object row per logical entry while keeping a multi-entry mutation (plus
any sibling-catalogue co-writes) all-or-nothing. ``namespace_payload_hashes``
is its decryption-free diff companion: an entry whose freshly-serialised
``payload_hash`` already matches the stored value need not be rewritten.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ......core.secure_object_write import SecureObjectWrite
from ......tests.master_key import EphemeralMasterKeyProvider
from ...crypto.encrypted_columns import secure_object_key_digest
from ...errors import SecureObjectRevisionConflictError
from ...tests.engine_bootstrap import bootstrap_sqlite_engine
from .._secure_object_records import SecureObjectDeletion
from ._secure_objects_support import (
    SecureObjectRepository,
    SensitivityClass,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NS = "aeat-test"


def _write(key: str, body: bytes, *, expected_revision_id: str | None = None) -> SecureObjectWrite:
    return SecureObjectWrite(
        namespace=_NS,
        object_key=key,
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=datetime(2026, 1, 1, tzinfo=UTC),
        payload=body,
        expected_revision_id=expected_revision_id,
    )


@contextmanager
def _repo(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    engine = bootstrap_sqlite_engine(tmp_path / "batch.db")
    try:
        yield SecureObjectRepository(engine=engine)
    finally:
        engine.dispose()


def test_apply_batch_upserts_and_deletes_in_one_unit(tmp_path: Path) -> None:
    with EphemeralMasterKeyProvider(), _repo(tmp_path) as repo:
        repo.apply_batch((_write("alpha", b"alpha-1"), _write("beta", b"beta-1")))
        assert repo.exists(_NS, "alpha")
        assert repo.exists(_NS, "beta")

        # One batch: upsert alpha (new content) + new gamma, delete beta by digest.
        repo.apply_batch(
            (_write("alpha", b"alpha-2"), _write("gamma", b"gamma-1")),
            (SecureObjectDeletion(namespace=_NS, hashed_object_key=secure_object_key_digest("beta")),),
        )

        alpha = repo.load(_NS, "alpha", expected_class=SensitivityClass.FINANCIAL, max_supported_version=1)
        assert alpha is not None and alpha.payload == b"alpha-2"
        assert repo.exists(_NS, "gamma")
        assert not repo.exists(_NS, "beta")


def test_namespace_payload_hashes_keys_match_natural_key_digests(tmp_path: Path) -> None:
    with EphemeralMasterKeyProvider(), _repo(tmp_path) as repo:
        repo.apply_batch((_write("alpha", b"stable-body"), _write("beta", b"beta-body")))

        stored = repo.namespace_payload_hashes(_NS)
        assert set(stored) == {secure_object_key_digest("alpha"), secure_object_key_digest("beta")}
        # Every entry carries a content hash (drives the unchanged-skip diff).
        assert all(value for value in stored.values())
        # Stable across reads; a different namespace is empty.
        assert repo.namespace_payload_hashes(_NS) == stored
        assert repo.namespace_payload_hashes("cadrumo-test.absent") == {}


def test_apply_batch_is_atomic_on_failure(tmp_path: Path) -> None:
    """A failure mid-batch rolls back every other upsert and deletion.

    The all-or-nothing guarantee is the whole reason per-row storage can replace
    the single-blob save without losing the multi-catalogue co-write atomicity.
    A stale ``expected_revision_id`` raises *inside* the unit of work; the sibling
    upsert and the deletion in the same batch must not survive.
    """
    with EphemeralMasterKeyProvider(), _repo(tmp_path) as repo:
        repo.apply_batch((_write("keep", b"keep-body"), _write("victim", b"victim-body")))

        with pytest.raises(SecureObjectRevisionConflictError):
            repo.apply_batch(
                (
                    _write("added", b"added-body"),
                    # Stale optimistic-concurrency guard -> conflict inside the session.
                    _write("keep", b"keep-body-2", expected_revision_id="0" * 64),
                ),
                (SecureObjectDeletion(namespace=_NS, hashed_object_key=secure_object_key_digest("victim")),),
            )

        # Nothing from the failed batch committed.
        assert not repo.exists(_NS, "added"), "sibling upsert must roll back"
        assert repo.exists(_NS, "victim"), "deletion must roll back"
        kept = repo.load(_NS, "keep", expected_class=SensitivityClass.FINANCIAL, max_supported_version=1)
        assert kept is not None and kept.payload == b"keep-body", "conflicting upsert must roll back"
