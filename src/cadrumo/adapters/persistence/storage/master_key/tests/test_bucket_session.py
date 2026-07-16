"""Tests for the per-bucket `BucketSession` instance-scoped unlock state."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TypedDict

import pytest

from ...bucket import BucketLockedError
from ...errors import StorageValidationError
from .._active_session import (
    activate_session,
    close_active_bucket_session,
    current_active_bucket_session,
    has_active_bucket_session,
)
from .._bucket_session import (
    BucketSession,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_KEK = bytes(range(32))
_DEK = bytes(range(32, 64))
_BUCKET_ID = "66666666-6666-4666-8666-666666666666"
_OTHER_BUCKET_ID = "77777777-7777-4777-8777-777777777777"


def _open_session(
    *,
    bucket_id: str = _BUCKET_ID,
    kek: bytes = _KEK,
    dek: bytes = _DEK,
    idle_minutes: int = 15,
    opened_at: datetime = _NOW,
    storage_root: Path | None = None,
) -> BucketSession:
    return BucketSession.open(
        bucket_id=bucket_id,
        kek=kek,
        dek=dek,
        idle_minutes=idle_minutes,
        opened_at=opened_at,
        storage_root=storage_root,
    )


def test_open_round_trip_exposes_kek_and_dek() -> None:
    storage_root = Path("var") / "profiles"
    session = _open_session(storage_root=storage_root)

    assert session.kek == _KEK
    assert session.dek == _DEK
    assert session.bucket_id == _BUCKET_ID
    assert session.storage_root == storage_root.resolve()
    assert session.sealed is False


def test_close_zeroises_kek_and_dek_buffers() -> None:
    session = _open_session()
    kek_buffer = session._kek_buffer
    dek_buffer = session._dek_buffer

    session.close()

    assert bytes(kek_buffer) == bytes(32)
    assert bytes(dek_buffer) == bytes(32)
    assert session.sealed is True


def test_reads_against_sealed_session_raise_bucket_locked() -> None:
    session = _open_session()
    session.close()

    with pytest.raises(BucketLockedError) as kek_exc:
        _ = session.kek
    assert kek_exc.value.bucket_id == _BUCKET_ID

    with pytest.raises(BucketLockedError):
        _ = session.dek


def test_close_is_idempotent() -> None:
    session = _open_session()

    session.close()
    session.close()

    assert session.sealed is True


def test_close_active_bucket_session_closes_evicts_and_repeats_as_no_op() -> None:
    session = _open_session()
    kek_buffer = session._kek_buffer
    dek_buffer = session._dek_buffer

    with activate_session(session):
        assert current_active_bucket_session() is session
        assert has_active_bucket_session() is True

        close_active_bucket_session()

        assert current_active_bucket_session() is None
        assert has_active_bucket_session() is False
        assert session.sealed is True
        assert bytes(kek_buffer) == bytes(32)
        assert bytes(dek_buffer) == bytes(32)

        close_active_bucket_session()

        assert current_active_bucket_session() is None
        assert has_active_bucket_session() is False


def test_close_inner_active_session_restores_unclosed_outer_after_token_reset() -> None:
    outer = _open_session()
    inner = _open_session(
        bucket_id=_OTHER_BUCKET_ID,
        kek=b"i" * 32,
        dek=b"I" * 32,
    )

    with activate_session(outer):
        with activate_session(inner):
            assert current_active_bucket_session() is inner

            close_active_bucket_session()

            assert current_active_bucket_session() is None
            assert has_active_bucket_session() is False
            assert inner.sealed is True

        assert current_active_bucket_session() is outer
        assert has_active_bucket_session() is True
        assert outer.sealed is False
        assert outer.dek == _DEK

        close_active_bucket_session()

        assert current_active_bucket_session() is None
        assert has_active_bucket_session() is False

    assert current_active_bucket_session() is None
    assert has_active_bucket_session() is False


def test_close_active_bucket_session_evicts_already_sealed_binding() -> None:
    session = _open_session()
    session.close()

    with activate_session(session):
        assert current_active_bucket_session() is session
        assert has_active_bucket_session() is True

        close_active_bucket_session()

        assert current_active_bucket_session() is None
        assert has_active_bucket_session() is False


def test_two_sessions_do_not_alias_buffers() -> None:
    session_a = _open_session(bucket_id=_BUCKET_ID, kek=b"a" * 32, dek=b"A" * 32)
    session_b = _open_session(bucket_id=_OTHER_BUCKET_ID, kek=b"b" * 32, dek=b"B" * 32)

    buffer_a = session_a._kek_buffer
    buffer_b = session_b._kek_buffer
    assert id(buffer_a) != id(buffer_b)

    # Mutating one buffer does not bleed into the other.
    buffer_a[0] = 0xFF
    assert session_b.kek == b"b" * 32


def test_is_expired_before_and_after_idle_window() -> None:
    session = _open_session(idle_minutes=15, opened_at=_NOW)

    inside_window = _NOW + timedelta(minutes=15) - timedelta(seconds=1)
    past_window = _NOW + timedelta(minutes=15) + timedelta(seconds=1)

    assert session.is_expired(inside_window) is False
    assert session.is_expired(past_window) is True


def test_touch_resets_idle_deadline() -> None:
    session = _open_session(idle_minutes=15, opened_at=_NOW)
    past_window = _NOW + timedelta(minutes=15) + timedelta(seconds=1)
    assert session.is_expired(past_window) is True

    session.touch(past_window)

    assert session.is_expired(past_window + timedelta(minutes=14)) is False
    assert session.is_expired(past_window + timedelta(minutes=16)) is True


class _KeyMaterialOverride(TypedDict, total=False):
    """The subset of :func:`_open_session`'s kwargs this parametrize overrides.

    A plain ``dict[str, bytes]`` cannot be ``**``-unpacked against
    ``_open_session``'s heterogeneously-typed kwargs (``bucket_id: str``,
    ``idle_minutes: int``, ``opened_at: datetime`` alongside ``kek``/``dek:
    bytes``): the checker cannot prove the dict carries only the two
    ``bytes``-typed keys. This ``TypedDict`` names exactly those two optional
    keys so the ``**`` unpack matches per-key against ``_open_session``'s real
    parameter types.
    """

    kek: bytes
    dek: bytes


@pytest.mark.parametrize(
    ("key_material", "message"),
    [
        ({"kek": b"x" * 16}, "kek must be exactly 32 bytes"),
        ({"dek": b"x" * 16}, "dek must be exactly 32 bytes"),
    ],
    ids=("kek", "dek"),
)
def test_open_rejects_wrong_size_key_material(key_material: _KeyMaterialOverride, message: str) -> None:
    with pytest.raises(StorageValidationError, match=message) as exc_info:
        _open_session(**key_material)
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_validation"


def test_open_rejects_empty_bucket_id() -> None:
    with pytest.raises(StorageValidationError, match="bucket_id must be non-empty") as exc_info:
        _open_session(bucket_id="")
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_validation"


def test_open_rejects_non_positive_idle_minutes() -> None:
    with pytest.raises(StorageValidationError, match="idle_minutes must be a strict positive integer") as exc_info:
        _open_session(idle_minutes=0)
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_validation"
