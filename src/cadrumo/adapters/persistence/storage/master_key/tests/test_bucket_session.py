"""Tests for the per-bucket `BucketSession` instance-scoped unlock state."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict

import pytest

from ......core.errors.hierarchy import CoreValidationError
from ...bucket.errors import BucketLockedError
from ...errors import StorageValidationError
from ..active_session import (
    activate_session,
    active_bucket_session_serves,
    close_active_bucket_session,
    current_active_bucket_session,
    has_active_bucket_session,
)
from ..bucket_session import (
    BucketSession,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_KEK = bytes(range(32))
_DEK = bytes(range(32, 64))
_BUCKET_ID = "66666666-6666-4666-8666-666666666666"
_OTHER_BUCKET_ID = "77777777-7777-4777-8777-777777777777"
_NAIVE = datetime(2026, 5, 14, 12, 0, 0)
_PLUS_ONE = datetime(2026, 5, 14, 13, 0, 0, tzinfo=timezone(timedelta(hours=1)))


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


@pytest.mark.parametrize("opened_at", (_NAIVE, _PLUS_ONE), ids=("naive", "non-utc"))
def test_open_refuses_non_utc_lifecycle_start(opened_at: datetime) -> None:
    with pytest.raises(CoreValidationError, match="UTC"):
        _open_session(opened_at=opened_at)


@pytest.mark.parametrize("invalid_instant", (_NAIVE, _PLUS_ONE), ids=("naive", "non-utc"))
def test_open_resumed_refuses_non_utc_lifecycle_instants(invalid_instant: datetime) -> None:
    with pytest.raises(CoreValidationError, match="UTC"):
        BucketSession.open_resumed(
            bucket_id=_BUCKET_ID,
            dek=_DEK,
            idle_minutes=15,
            opened_at=invalid_instant,
            idle_deadline=_NOW + timedelta(minutes=15),
            absolute_deadline=_NOW + timedelta(minutes=30),
        )

    with pytest.raises(CoreValidationError, match="UTC"):
        BucketSession.open_resumed(
            bucket_id=_BUCKET_ID,
            dek=_DEK,
            idle_minutes=15,
            opened_at=_NOW,
            idle_deadline=invalid_instant,
            absolute_deadline=_NOW + timedelta(minutes=30),
        )

    with pytest.raises(CoreValidationError, match="UTC"):
        BucketSession.open_resumed(
            bucket_id=_BUCKET_ID,
            dek=_DEK,
            idle_minutes=15,
            opened_at=_NOW,
            idle_deadline=_NOW + timedelta(minutes=15),
            absolute_deadline=invalid_instant,
        )


def test_open_resumed_utc_session_preserves_expiry_semantics() -> None:
    session = BucketSession.open_resumed(
        bucket_id=_BUCKET_ID,
        dek=_DEK,
        idle_minutes=15,
        opened_at=_NOW,
        idle_deadline=_NOW + timedelta(minutes=15),
        absolute_deadline=_NOW + timedelta(minutes=30),
    )

    refreshed_at = _NOW + timedelta(minutes=10)
    session.touch(refreshed_at)

    assert session.opened_at == _NOW
    assert session.idle_deadline == refreshed_at + timedelta(minutes=15)
    assert session.is_expired(_NOW + timedelta(minutes=24)) is False
    assert session.is_expired(_NOW + timedelta(minutes=30)) is True


@pytest.mark.parametrize("invalid_now", (_NAIVE, _PLUS_ONE), ids=("naive", "non-utc"))
def test_touch_and_expiry_refuse_non_utc_lifecycle_instants(invalid_now: datetime) -> None:
    session = _open_session()

    with pytest.raises(CoreValidationError, match="UTC"):
        session.touch(invalid_now)
    with pytest.raises(CoreValidationError, match="UTC"):
        session.is_expired(invalid_now)


def test_routed_settings_reuses_one_derivation_for_one_source() -> None:
    """The session answers the repeated route question once.

    A single profile write resolves this bucket's route three times, once
    per repository it constructs. Each derivation re-validates the whole
    settings model and re-resolves every configured path against the
    filesystem, so recomputing it was the dominant cost of the write.
    """
    from ......core.config import Settings, settings_for_active_profile_bucket

    session = _open_session()
    source = Settings()

    first = session.routed_settings(source)
    second = session.routed_settings(source)

    assert first is second
    assert first == settings_for_active_profile_bucket(_BUCKET_ID, source)


def test_routed_settings_recomputes_when_the_source_changes() -> None:
    """The memo is keyed on the source, not merely on this bucket's identity.

    Two callers can legitimately ask for this bucket's route from different
    live settings; serving the first answer to the second would silently
    route the second caller through the first's configuration.
    """
    from ......core.config import Settings

    session = _open_session()
    source = Settings()
    other = Settings(cadrumo_file_lock_timeout_s=source.cadrumo_file_lock_timeout_s + 1)

    first = session.routed_settings(source)
    second = session.routed_settings(other)

    assert first is not second
    assert second.cadrumo_file_lock_timeout_s == other.cadrumo_file_lock_timeout_s
    assert session.routed_settings(other) is second


def test_routed_settings_refuses_a_sealed_session() -> None:
    """A sealed session owns nothing, memo included."""
    from ......core.config import Settings

    session = _open_session()
    session.routed_settings(Settings())
    session.close()

    with pytest.raises(BucketLockedError):
        session.routed_settings(Settings())


def test_two_sessions_never_share_a_routed_settings_answer() -> None:
    """Each session memoises only its OWN bucket's route.

    The substrate invariant is that no state keyed on a bucket may outlive
    a bucket switch; holding the memo on the session is what makes that
    structural rather than a discipline.
    """
    from ......core.config import Settings

    source = Settings()
    first = _open_session(bucket_id=_BUCKET_ID).routed_settings(source)
    second = _open_session(bucket_id=_OTHER_BUCKET_ID).routed_settings(source)

    assert first.cadrumo_active_profile == _BUCKET_ID
    assert second.cadrumo_active_profile == _OTHER_BUCKET_ID
    assert first.cadrumo_database_url != second.cadrumo_database_url


def test_acquire_engine_does_not_build_a_route_it_will_discard(tmp_path: Path) -> None:
    """The settings factory runs only when an engine must actually be resolved.

    The handle is cached for the session, so every access after the first
    ignored the settings it was handed. Building them eagerly cost a full
    settings validation per repository construction, three times per write.
    """
    from ......core.config import Settings, override_settings

    session = _open_session()
    builds = 0

    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None):
        settings = Settings(cadrumo_local_storage_root=tmp_path)

        def _route() -> Settings:
            nonlocal builds
            builds += 1
            return settings

        first = session.acquire_engine(_route)
        second = session.acquire_engine(_route)

    assert first is second
    assert builds == 1


def test_active_bucket_session_serves_matches_only_the_bound_bucket() -> None:
    """The reuse predicate discriminates the bucket; presence alone does not.

    This is the whole reason the predicate exists. Four application spans
    decided whether to reuse an ambient session, and two of them asked only
    whether SOME session was bound. With a session for one bucket ambient and
    a caller targeting another, that question answers "yes" and the caller
    proceeds to read or write the wrong profile's encrypted store under the
    wrong key. The second assertion is the discriminating one: if
    ``active_bucket_session_serves`` ever returns ``True`` for a foreign
    bucket it has become ``has_active_bucket_session`` and buys nothing.
    """
    session = _open_session(bucket_id=_BUCKET_ID)

    with activate_session(session):
        assert has_active_bucket_session() is True

        assert active_bucket_session_serves(_BUCKET_ID) is True
        assert active_bucket_session_serves(_OTHER_BUCKET_ID) is False


def test_active_bucket_session_serves_is_false_with_no_session_bound() -> None:
    """No bound session serves any bucket, including a well-formed id."""
    assert has_active_bucket_session() is False

    assert active_bucket_session_serves(_BUCKET_ID) is False
