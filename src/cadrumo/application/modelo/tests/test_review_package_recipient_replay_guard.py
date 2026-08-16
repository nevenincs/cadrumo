"""Recipient replay-guard ledger: encrypted roundtrip and anti-tautology proofs.

Exercises :mod:`~application.modelo._review_package_recipient_replay_guard`
against a REAL encrypted
:class:`~adapters.persistence.storage.SecureObjectRepository`
(:func:`~tests.secure_sql.isolated_runtime_profile` -- a genuine
``BUCKET_DEK_V1`` bucket, no mocks or fakes): mark a nonce consumed, confirm
the ledger roundtrips through the encrypted boundary with strict equality,
confirm the ledger is real ciphertext at rest, confirm a second
``mark_consumed`` for the same nonce is refused as a replay, and confirm a
corrupted on-disk payload is refused at load (the anti-tautology proof required
by ``aeat-quality-gates``).

See Also:
    :class:`~application.modelo.RecipientReplayGuardRepository`:
        Encrypted consumed-nonce ledger under test.
    :class:`~application.modelo.RecipientEncryptedPackage`:
        Transport envelope carrying the ``envelope_nonce_hex`` replay token.
    :func:`~entrypoints.cli._modelo_review_package_cli.review_package_decrypt`:
        CLI composition point that consumes the nonce after decryption.
"""

from __future__ import annotations

import contextvars
import secrets
import threading
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage import (
    MODELO_REVIEW_PACKAGE_RECIPIENT_REPLAY_GUARD_NAMESPACE as _NAMESPACE,
)
from ....adapters.persistence.storage import DecryptionError
from ....adapters.persistence.storage.sql import SecureObjectRow
from ....adapters.persistence.storage.sql.session import session_scope
from ....tests.secure_sql import isolated_runtime_profile
from .._review_package_recipient_replay_guard import (
    ConsumedNonceLedger,
    RecipientPackageReplayedError,
    RecipientReplayGuardRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)
_JOIN_TIMEOUT_S = 60.0


def _fresh_nonce_hex() -> str:
    return secrets.token_hex(32)


def test_load_returns_empty_ledger_when_absent(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="922171fc-7bb5-40c0-ac9a-11431b11a64f") as profile:
        repository = RecipientReplayGuardRepository(objects=profile.repository)
        assert repository.load() == ConsumedNonceLedger()


def test_is_consumed_is_false_before_and_true_after_mark_consumed(tmp_path: Path) -> None:
    nonce_hex = _fresh_nonce_hex()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="81f3bb9d-313c-444b-9475-9d32310484dc") as profile:
        repository = RecipientReplayGuardRepository(objects=profile.repository)
        assert repository.is_consumed(nonce_hex) is False

        repository.mark_consumed(nonce_hex, consumed_at=_NOW)

        assert repository.is_consumed(nonce_hex) is True


def test_mark_consumed_then_load_roundtrips_with_strict_equality(tmp_path: Path) -> None:
    nonce_hex = _fresh_nonce_hex()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="1f8ea194-51c7-4d6c-abf4-df4043cc5e1a") as profile:
        repository = RecipientReplayGuardRepository(objects=profile.repository)

        updated = repository.mark_consumed(nonce_hex, consumed_at=_NOW)
        reloaded = repository.load()

    assert reloaded == updated
    assert len(reloaded.records) == 1
    record = reloaded.records[0]
    assert record.nonce_hex == nonce_hex
    assert record.consumed_at == _NOW


@pytest.mark.parametrize(
    "consumed_at",
    (
        pytest.param(datetime(2026, 7, 3, 12, 0), id="naive"),
        pytest.param(datetime(2026, 7, 3, 14, 0, tzinfo=timezone(timedelta(hours=2))), id="non-utc"),
    ),
)
def test_mark_consumed_refuses_a_naive_or_non_utc_consumed_at(tmp_path: Path, consumed_at: datetime) -> None:
    """A consumed-nonce record must carry one explicit UTC ``consumed_at`` instant."""
    nonce_hex = _fresh_nonce_hex()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="e3b1b181-438d-4f22-867f-5e981d979775") as profile:
        repository = RecipientReplayGuardRepository(objects=profile.repository)
        with pytest.raises(ValidationError, match="datetime must be"):
            repository.mark_consumed(nonce_hex, consumed_at=consumed_at)


def test_ledger_is_never_stored_as_plaintext(tmp_path: Path) -> None:
    nonce_hex = _fresh_nonce_hex()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="4384aad2-586d-4e57-bafa-78c2d2c98031") as profile:
        repository = RecipientReplayGuardRepository(objects=profile.repository)
        repository.mark_consumed(nonce_hex, consumed_at=_NOW)

        from sqlalchemy import select

        with session_scope(profile.repository._engine) as session:
            row = session.execute(
                select(SecureObjectRow).where(SecureObjectRow.namespace == _NAMESPACE.namespace),
            ).scalar_one()
            ciphertext_bytes = bytes(row.payload)

    assert nonce_hex.encode("utf-8") not in ciphertext_bytes


def test_mark_consumed_twice_refuses_as_replay(tmp_path: Path) -> None:
    """Real behaviour: presenting the same nonce a second time is a replay refusal."""
    nonce_hex = _fresh_nonce_hex()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="c565705d-eaa8-411f-b420-8296f3c19c03") as profile:
        repository = RecipientReplayGuardRepository(objects=profile.repository)
        repository.mark_consumed(nonce_hex, consumed_at=_NOW)

        with pytest.raises(RecipientPackageReplayedError):
            repository.mark_consumed(nonce_hex, consumed_at=_NOW)

        # The ledger still carries exactly one record -- the refused replay
        # attempt did not silently append a duplicate.
        assert len(repository.load().records) == 1


def test_concurrent_same_nonce_consumption_allows_exactly_one_success(tmp_path: Path) -> None:
    """Concurrent presentations of one genuine nonce yield one consume and replay refusals."""
    writer_count = 8
    nonce_hex = _fresh_nonce_hex()
    successes: list[ConsumedNonceLedger] = []
    replay_refusals: list[RecipientPackageReplayedError] = []
    unexpected: list[Exception] = []

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="7a6da921-b01a-47c6-965b-fcf8280e83d3") as profile:
        repository = RecipientReplayGuardRepository(objects=profile.repository)
        gate = threading.Barrier(writer_count)

        def consume() -> None:
            try:
                gate.wait()
                successes.append(repository.mark_consumed(nonce_hex, consumed_at=_NOW))
            except RecipientPackageReplayedError as exc:
                replay_refusals.append(exc)
            except Exception as exc:
                unexpected.append(exc)

        threads = [
            threading.Thread(target=contextvars.copy_context().run, args=(consume,)) for _ in range(writer_count)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=_JOIN_TIMEOUT_S)

        assert not [thread for thread in threads if thread.is_alive()], "a replay consumer deadlocked"
        assert unexpected == []
        assert len(successes) == 1
        assert len(replay_refusals) == writer_count - 1
        persisted = repository.load()
        assert [record.nonce_hex for record in persisted.records] == [nonce_hex]


def test_concurrent_distinct_nonce_consumption_preserves_every_record(tmp_path: Path) -> None:
    """Concurrent distinct nonce consumes survive revision conflicts without lost updates."""
    nonces = tuple(_fresh_nonce_hex() for _ in range(8))
    unexpected: list[Exception] = []

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="c7b05088-3df5-4dc7-92aa-c364cf37a431") as profile:
        repository = RecipientReplayGuardRepository(objects=profile.repository)
        gate = threading.Barrier(len(nonces))

        def consume(nonce_hex: str) -> None:
            try:
                gate.wait()
                repository.mark_consumed(nonce_hex, consumed_at=_NOW)
            except Exception as exc:
                unexpected.append(exc)

        threads = [
            threading.Thread(target=contextvars.copy_context().run, args=(consume, nonce_hex)) for nonce_hex in nonces
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=_JOIN_TIMEOUT_S)

        assert not [thread for thread in threads if thread.is_alive()], "a replay consumer deadlocked"
        assert unexpected == []
        persisted = repository.load()
        assert len(persisted.records) == len(nonces)
        assert {record.nonce_hex for record in persisted.records} == set(nonces)


def test_two_buckets_maintain_independent_ledgers(tmp_path: Path) -> None:
    """Two profiles' replay ledgers never collide -- per-bucket scoping."""
    shared_nonce_hex = _fresh_nonce_hex()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="1d9626a5-f7a1-4615-a8c3-dd7073664c10") as profile_one:
        RecipientReplayGuardRepository(objects=profile_one.repository).mark_consumed(
            shared_nonce_hex,
            consumed_at=_NOW,
        )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bd58b114-6a62-49ff-b412-07122fe6a41f") as profile_two:
        repository_two = RecipientReplayGuardRepository(objects=profile_two.repository)
        # The same nonce value is unconsumed in the second bucket's own ledger.
        assert repository_two.is_consumed(shared_nonce_hex) is False
        repository_two.mark_consumed(shared_nonce_hex, consumed_at=_NOW)
        assert len(repository_two.load().records) == 1


def test_load_raises_on_corrupted_ciphertext(tmp_path: Path) -> None:
    """Anti-tautology proof: a corrupted on-disk payload must not silently deserialise.

    Directly mutates the raw stored ciphertext bytes (bypassing the
    repository's encrypt path) and confirms ``load`` refuses rather than
    returning a plausible-looking (and dangerously permissive, since it
    would re-open every previously-consumed nonce to replay) empty ledger.
    """
    nonce_hex = _fresh_nonce_hex()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="b59a72bb-15e7-4c8c-94c0-691d11dc1449") as profile:
        repository = RecipientReplayGuardRepository(objects=profile.repository)
        repository.mark_consumed(nonce_hex, consumed_at=_NOW)

        from sqlalchemy import select, update

        with session_scope(profile.repository._engine) as session:
            row = session.execute(
                select(SecureObjectRow).where(SecureObjectRow.namespace == _NAMESPACE.namespace),
            ).scalar_one()
            corrupted_payload = bytes(row.payload)[:-1] + bytes([bytes(row.payload)[-1] ^ 0xFF])
            session.execute(
                update(SecureObjectRow)
                .where(SecureObjectRow.namespace == _NAMESPACE.namespace)
                .values(payload=corrupted_payload),
            )

        with pytest.raises(DecryptionError):
            repository.load()


__all__: list[str] = []
