"""The plaintext date-index reads carry the session check themselves.

Three methods on the transaction repository read the derived date index
through a raw scope over the secure-object engine. Taking that engine is the
one route into the bucket database that skips
``SecureObjectRepository._check_session_freshness`` -- the check every
operation on that repository otherwise applies -- so a raw read served a
sealed session, an idle-expired session, or a session that had moved to
another bucket, with nothing to stop it.

Those three were never exposed in practice, and that is the point. Each is
reached only after a guarded ``load``, so the check fired earlier in the call
and the raw read inherited its protection. That is protection by call ORDER:
it holds exactly until someone adds an entry point that reaches a raw read
first, nothing states the ordering, and no test would notice it changing.

The reads now go through ``guarded_session_scope``, which applies the check at
the read itself. This pins that, driving the private method DIRECTLY -- with
no guarded call in front of it -- because reaching it through a public path
would re-establish the ordering that used to be the whole protection and prove
nothing about the read.

The index carries no financial content by design (routing keys only,
``SensitivityClass.CACHE``, enforced by a live-schema assertion in
``test_transaction_date_index.py``). What the session check governs here is
therefore not confidentiality of amounts but the idle lock itself: an operator
who walked away should not have a profile's transaction ids and filing dates
still answering queries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from .....adapters.persistence.storage.errors import StorageValidationError
from .....adapters.persistence.storage.master_key.active_session import activate_session
from .....adapters.persistence.storage.master_key.bucket_session import BucketSession
from .....core.time.clock import now as _utc_now
from .....tests.secure_sql import isolated_runtime_profile
from ..transactions import TransactionCatalogueRepository

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "44444444-4444-4444-8444-444444444444"


def _foreign_session() -> BucketSession:
    """Open a real session serving a DIFFERENT bucket."""
    return BucketSession.open(
        bucket_id=str(uuid4()),
        kek=b"k" * 32,
        dek=b"d" * 32,
        idle_minutes=30,
        opened_at=_utc_now(),
    )


def test_the_raw_index_read_refuses_when_the_session_serves_another_bucket(tmp_path: Path) -> None:
    """DISCRIMINATING: the read is checked at the read, not by whatever ran first.

    Driven straight at the private method. Going through a public entry point
    would run a guarded load first and prove only that the OLD incidental
    ordering still holds.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)

        with activate_session(_foreign_session()), pytest.raises(StorageValidationError) as raised:
            repository._all_date_index_rows()

    assert raised.value.translated_message == "errors.storage.runtime.not_ready"


def test_the_same_read_succeeds_under_its_own_session(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: the refusal must be the session, not a broken read.

    Without this, a method that had stopped working for any reason -- a renamed
    table, a closed engine, a fixture that never provisioned -- would satisfy
    the assertion above while proving nothing about the guard.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)

        rows = repository._all_date_index_rows()

    assert rows == {}
