"""Tests for the per-bucket `BucketSession` instance-scoped unlock state."""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ...bucket._errors import BucketLockedError
from ...errors import StorageValidationError
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
) -> BucketSession:
    return BucketSession.open(
        bucket_id=bucket_id,
        kek=kek,
        dek=dek,
        idle_minutes=idle_minutes,
        opened_at=opened_at,
    )


def test_open_round_trip_exposes_kek_and_dek() -> None:
    session = _open_session()

    assert session.kek == _KEK
    assert session.dek == _DEK
    assert session.bucket_id == _BUCKET_ID
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


def test_open_rejects_wrong_size_kek() -> None:
    with pytest.raises(StorageValidationError, match="kek must be exactly 32 bytes") as exc_info:
        _open_session(kek=b"x" * 16)
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_validation"


def test_open_rejects_wrong_size_dek() -> None:
    with pytest.raises(StorageValidationError, match="dek must be exactly 32 bytes") as exc_info:
        _open_session(dek=b"x" * 16)
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_validation"


def test_open_rejects_empty_bucket_id() -> None:
    with pytest.raises(StorageValidationError, match="bucket_id must be non-empty") as exc_info:
        _open_session(bucket_id="")
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_validation"


def test_open_rejects_non_positive_idle_minutes() -> None:
    with pytest.raises(StorageValidationError, match="idle_minutes must be a strict positive integer") as exc_info:
        _open_session(idle_minutes=0)
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_validation"


def test_module_has_no_classvar_typed_attributes() -> None:
    """Static AST guard: `BucketSession` keeps zero `ClassVar` state.

    The substrate invariant forbids module-global mutable state on
    the master-key surface. This guard catches a regression that would
    re-introduce a process-lifetime cache by typing it `ClassVar[...]`.
    """

    source_path = Path(inspect.getsourcefile(BucketSession) or "")
    module = ast.parse(source_path.read_text(encoding="utf-8"))

    offenders: list[str] = []
    for node in ast.walk(module):
        if isinstance(node, ast.AnnAssign):
            annotation = ast.unparse(node.annotation)
            if "ClassVar" in annotation:
                offenders.append(ast.unparse(node))

    assert offenders == [], f"ClassVar attributes are forbidden on this module: {offenders}"


def test_module_derives_dispose_settings_from_loaded_settings() -> None:
    """Engine eviction must not bypass central settings with a direct Settings constructor."""

    source_path = Path(inspect.getsourcefile(BucketSession) or "")
    module = ast.parse(source_path.read_text(encoding="utf-8"))

    direct_settings_constructors: list[str] = []
    for node in ast.walk(module):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Settings":
            direct_settings_constructors.append(ast.unparse(node))

    assert direct_settings_constructors == []
