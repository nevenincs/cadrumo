"""One loaded transaction catalogue pinned to the revision a ledger action resolved against."""

from __future__ import annotations

from typing import Any, cast

import pytest

from ..persistence_ports import LedgerPersistenceConflictError
from ..pinned_transaction_repository import PinnedRevisionedTransactionRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _RecordingRepository:
    bucket_id = "9f0c2a3e-8a52-4c1d-9a51-6d1e2f3a4b5c"

    def __init__(self) -> None:
        self.commits: list[tuple[object, str, tuple[object, ...]]] = []

    def save_if_revision_with_secure_object_writes(
        self, catalogue: object, *, expected_revision_id: str, extra_writes: tuple[object, ...]
    ) -> None:
        self.commits.append((catalogue, expected_revision_id, extra_writes))


def _pinned(repository: _RecordingRepository, catalogue: object) -> PinnedRevisionedTransactionRepository:
    return PinnedRevisionedTransactionRepository(
        repository=cast(Any, repository),
        catalogue=cast(Any, catalogue),
        revision_id="rev-1",
        action="split",
    )


def test_reads_return_the_pinned_snapshot_and_revision() -> None:
    catalogue = object()
    pinned = _pinned(_RecordingRepository(), catalogue)

    assert pinned.load() is catalogue
    assert pinned.load_revisioned() == (catalogue, "rev-1")
    assert pinned.bucket_id == _RecordingRepository.bucket_id


def test_every_unrevisioned_write_refuses_and_names_the_action() -> None:
    repository = _RecordingRepository()
    pinned = _pinned(repository, object())
    catalogue = cast(Any, object())
    transaction = cast(Any, object())

    for write in (
        lambda: pinned.save(catalogue),
        lambda: pinned.save_with_secure_object_writes(catalogue, ()),
        lambda: pinned.replace_if_current_with_secure_object_writes(transaction, transaction, ()),
    ):
        with pytest.raises(LedgerPersistenceConflictError, match="ledger split requires the pinned catalogue revision"):
            write()
    assert repository.commits == []


def test_a_write_against_another_revision_refuses_without_committing() -> None:
    repository = _RecordingRepository()
    pinned = _pinned(repository, object())

    with pytest.raises(LedgerPersistenceConflictError, match="ledger split attempted to write against another"):
        pinned.save_if_revision_with_secure_object_writes(
            cast(Any, object()), expected_revision_id="rev-2", extra_writes=()
        )
    assert repository.commits == []


def test_a_write_against_the_pinned_revision_commits_through_the_repository() -> None:
    repository = _RecordingRepository()
    pinned = _pinned(repository, object())
    replacement = object()
    writes = (object(),)

    pinned.save_if_revision_with_secure_object_writes(
        cast(Any, replacement), expected_revision_id="rev-1", extra_writes=cast(Any, writes)
    )

    assert repository.commits == [(replacement, "rev-1", writes)]
