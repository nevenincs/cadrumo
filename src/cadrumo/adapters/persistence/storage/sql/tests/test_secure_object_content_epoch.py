"""The store's content epoch moves on every write, rewrite and deletion, and on nothing else."""

from __future__ import annotations

from pathlib import Path

import pytest

from ......core.classification.policies import SensitivityClass
from ......core.secure_object_write import SecureObjectWrite
from ......core.time.clock import now
from .secure_objects_support import ephemeral_secure_repo

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NAMESPACE = "cadrumo-test.content.epoch"
_OTHER_NAMESPACE = "cadrumo-test.content.epoch.other"
# The epoch digests no write time; one instant keeps every write here alike.
_WRITTEN_AT = now()


def _write(key: str, payload: bytes, namespace: str = _NAMESPACE) -> SecureObjectWrite:
    return SecureObjectWrite(
        namespace=namespace,
        object_key=key,
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=_WRITTEN_AT,
        payload=payload,
    )


def test_reading_leaves_the_epoch_where_it_was(tmp_path: Path) -> None:
    with ephemeral_secure_repo(tmp_path, "epoch.db") as (_path, _engine, repo):
        repo.save_many((_write("alpha", b"one"),))
        before = repo.content_epoch()
        repo.load(_NAMESPACE, "alpha", expected_class=SensitivityClass.FINANCIAL, max_supported_version=1)

        assert repo.content_epoch() == before


def test_an_insert_a_rewrite_and_a_deletion_in_any_namespace_each_move_the_epoch(tmp_path: Path) -> None:
    with ephemeral_secure_repo(tmp_path, "epoch.db") as (_path, _engine, repo):
        empty = repo.content_epoch()
        repo.save_many((_write("alpha", b"one"),))
        inserted = repo.content_epoch()
        repo.save_many((_write("alpha", b"two"),))
        rewritten = repo.content_epoch()
        repo.save_many((_write("beta", b"one", namespace=_OTHER_NAMESPACE),))
        elsewhere = repo.content_epoch()
        assert repo.delete(_OTHER_NAMESPACE, "beta")
        deleted = repo.content_epoch()

        epochs = [empty, inserted, rewritten, elsewhere]
        assert len(set(epochs)) == len(epochs)
        assert deleted == rewritten, "removing the only row added since restores the store it was"


def test_a_write_to_an_excluded_namespace_leaves_the_epoch_and_any_other_moves_it(tmp_path: Path) -> None:
    excluded = frozenset({_OTHER_NAMESPACE})
    with ephemeral_secure_repo(tmp_path, "epoch.db") as (_path, _engine, repo):
        repo.save_many((_write("alpha", b"one"),))
        before = repo.content_epoch(excluding=excluded)
        repo.save_many((_write("beta", b"one", namespace=_OTHER_NAMESPACE),))

        assert repo.content_epoch(excluding=excluded) == before
        assert repo.content_epoch() != before

        repo.save_many((_write("alpha", b"two"),))

        assert repo.content_epoch(excluding=excluded) != before
