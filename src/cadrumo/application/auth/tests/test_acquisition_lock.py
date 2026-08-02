"""Tests for crash-recoverable auth acquisition locks."""

from __future__ import annotations

import os
import pathlib
import socket
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ....core import AuthProviderKind
from ....core.config import Settings
from ....core.external_constants import UTF_8_ENCODING
from .._acquisition_lock import (
    AuthAcquisitionLockedError,
    AuthAcquisitionLockRecord,
    AuthAcquisitionLockState,
    _remove_lock_file_if_unchanged,
    acquire_auth_acquisition_lock,
    auth_acquisition_lock_path,
    clear_auth_acquisition_lock,
    inspect_auth_acquisition_lock,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_STALE_LOCK_INSPECTION_AT = datetime(2026, 5, 26, 14, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _active_profile() -> Iterator[None]:
    from ....core.config import override_settings

    with override_settings(cadrumo_active_profile="operator"):
        yield


def _settings(tmp_path: Path) -> Settings:
    """Build a validated Settings instance with the tokens dir pinned.

    Direct constructor kwargs route through the pydantic validator chain;
    the previous ``model_copy(update=)`` form bypassed validators per
    pydantic v2 semantics.
    """
    return Settings(cadrumo_token_dir=tmp_path / "tokens")


def test_auth_acquisition_lock_blocks_second_live_owner(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    with acquire_auth_acquisition_lock(
        settings,
        AuthProviderKind.CLAVE_MOVIL,
        ttl_seconds=300,
        operation="test-auth-login",
    ) as record:
        status = inspect_auth_acquisition_lock(settings, AuthProviderKind.CLAVE_MOVIL)
        assert status.state is AuthAcquisitionLockState.HELD
        assert status.locked is True
        assert status.record == record

        with (
            pytest.raises(AuthAcquisitionLockedError) as excinfo,
            acquire_auth_acquisition_lock(
                settings,
                AuthProviderKind.CLAVE_MOVIL,
                ttl_seconds=300,
                operation="test-auth-login",
            ),
        ):
            pass
        assert excinfo.value.context is not None
        assert excinfo.value.context["state"] == "held"
        assert excinfo.value.context["pid"] == os.getpid()

    final_status = inspect_auth_acquisition_lock(settings, AuthProviderKind.CLAVE_MOVIL)
    assert final_status.state is AuthAcquisitionLockState.ABSENT


def test_auth_acquisition_lock_recovers_expired_owner(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    path = auth_acquisition_lock_path(settings, AuthProviderKind.CLAVE_MOVIL)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = _STALE_LOCK_INSPECTION_AT
    stale = AuthAcquisitionLockRecord(
        provider_kind=AuthProviderKind.CLAVE_MOVIL,
        profile_name="operator",
        pid=os.getpid(),
        hostname=socket.gethostname(),
        created_at=now - timedelta(minutes=20),
        expires_at=now - timedelta(minutes=10),
        operation="crashed-auth-login",
    )
    path.write_text(stale.model_dump_json(), encoding=UTF_8_ENCODING)

    status = inspect_auth_acquisition_lock(settings, AuthProviderKind.CLAVE_MOVIL, now=now)
    assert status.state is AuthAcquisitionLockState.STALE
    assert status.recoverable is True
    assert status.reason == "lock expired"

    with acquire_auth_acquisition_lock(
        settings,
        AuthProviderKind.CLAVE_MOVIL,
        ttl_seconds=300,
        operation="test-auth-login",
    ) as recovered:
        assert recovered.operation == "test-auth-login"
        assert recovered.created_at > stale.created_at

    assert not path.exists()


def test_auth_acquisition_lock_recovers_corrupt_metadata(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    path = auth_acquisition_lock_path(settings, AuthProviderKind.CLAVE_MOVIL)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding=UTF_8_ENCODING)

    status = inspect_auth_acquisition_lock(settings, AuthProviderKind.CLAVE_MOVIL)
    assert status.state is AuthAcquisitionLockState.CORRUPT
    assert status.recoverable is True

    with acquire_auth_acquisition_lock(
        settings,
        AuthProviderKind.CLAVE_MOVIL,
        ttl_seconds=300,
        operation="test-auth-login",
    ):
        held_status = inspect_auth_acquisition_lock(settings, AuthProviderKind.CLAVE_MOVIL)
        assert held_status.state is AuthAcquisitionLockState.HELD

    assert not path.exists()


def test_auth_acquisition_lock_can_be_cleared_for_manual_recovery(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    path = auth_acquisition_lock_path(settings, AuthProviderKind.CLAVE_MOVIL)

    with acquire_auth_acquisition_lock(
        settings,
        AuthProviderKind.CLAVE_MOVIL,
        ttl_seconds=300,
        operation="test-auth-login",
    ):
        cleared = clear_auth_acquisition_lock(
            settings,
            AuthProviderKind.CLAVE_MOVIL,
            reason="operator-confirmed-crash",
        )

    assert cleared.state is AuthAcquisitionLockState.HELD
    assert cleared.reason == "operator-confirmed-crash"
    assert cleared.recoverable is True
    assert not path.exists()


def _write_live_lock(
    settings: Settings,
    kind: AuthProviderKind,
    *,
    bucket_id: str,
    now: datetime,
) -> Path:
    """Write a real, live (unexpired, running-owner) lock file and return its path."""
    path = auth_acquisition_lock_path(settings, kind, bucket_id=bucket_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = AuthAcquisitionLockRecord(
        provider_kind=kind,
        profile_name=bucket_id,
        pid=os.getpid(),
        hostname=socket.gethostname(),
        created_at=now,
        expires_at=now + timedelta(minutes=10),
        operation="live-auth-login",
    )
    path.write_text(record.model_dump_json(), encoding=UTF_8_ENCODING)
    return path


def test_clear_auth_acquisition_lock_is_target_scoped_across_providers(tmp_path: Path) -> None:
    """Clearing one provider's lock leaves an unrelated provider's real lock file intact."""
    settings = _settings(tmp_path)
    now = datetime.now(UTC)
    certificate_lock = _write_live_lock(settings, AuthProviderKind.CERTIFICATE, bucket_id="operator", now=now)
    clave_lock = _write_live_lock(settings, AuthProviderKind.CLAVE_MOVIL, bucket_id="operator", now=now)

    cleared = clear_auth_acquisition_lock(settings, AuthProviderKind.CERTIFICATE, bucket_id="operator")

    assert cleared.state is AuthAcquisitionLockState.HELD
    assert not certificate_lock.exists()
    assert clave_lock.exists(), "an unrelated provider's acquisition lock must survive a scoped clear"
    surviving = inspect_auth_acquisition_lock(settings, AuthProviderKind.CLAVE_MOVIL, bucket_id="operator")
    assert surviving.state is AuthAcquisitionLockState.HELD


def test_clear_auth_acquisition_lock_is_target_scoped_across_buckets(tmp_path: Path) -> None:
    """Clearing one bucket's provider lock leaves the same provider's lock for another bucket intact."""
    settings = _settings(tmp_path)
    now = datetime.now(UTC)
    target_lock = _write_live_lock(settings, AuthProviderKind.CERTIFICATE, bucket_id="bucket-a", now=now)
    other_lock = _write_live_lock(settings, AuthProviderKind.CERTIFICATE, bucket_id="bucket-b", now=now)

    clear_auth_acquisition_lock(settings, AuthProviderKind.CERTIFICATE, bucket_id="bucket-a")

    assert not target_lock.exists()
    assert other_lock.exists(), "another bucket's acquisition lock must survive a target-scoped clear"
    surviving = inspect_auth_acquisition_lock(settings, AuthProviderKind.CERTIFICATE, bucket_id="bucket-b")
    assert surviving.state is AuthAcquisitionLockState.HELD


def test_clear_auth_acquisition_lock_is_repeatable(tmp_path: Path) -> None:
    """Clearing a target repeatedly removes the real lock once, then reports absence truthfully."""
    settings = _settings(tmp_path)
    now = datetime.now(UTC)
    path = _write_live_lock(settings, AuthProviderKind.CLAVE_MOVIL, bucket_id="operator", now=now)

    first = clear_auth_acquisition_lock(settings, AuthProviderKind.CLAVE_MOVIL, bucket_id="operator", reason="reset-1")
    second = clear_auth_acquisition_lock(settings, AuthProviderKind.CLAVE_MOVIL, bucket_id="operator", reason="reset-2")
    third = clear_auth_acquisition_lock(settings, AuthProviderKind.CLAVE_MOVIL, bucket_id="operator", reason="reset-3")

    assert first.state is AuthAcquisitionLockState.HELD
    assert first.recoverable is True
    assert not path.exists()
    assert second.state is AuthAcquisitionLockState.ABSENT
    assert second.recoverable is False
    assert third.state is AuthAcquisitionLockState.ABSENT
    assert not path.exists()



class TestStaleRemovalIsCompareAndDelete:
    """A stale verdict authorises removing THOSE bytes, not the file's future.

    ``clear_auth_acquisition_lock`` and the recoverable branch of
    ``acquire_auth_acquisition_lock`` inspected a stale or corrupt record and
    then unlinked the path without binding the deletion to what they had just
    judged. A lock released and reacquired in that window was destroyed while
    its new owner believed it held it -- and that owner then issues a second
    Cl@ve petition, the exact duplicate this lock exists to prevent.
    """

    def _expired_record(self) -> AuthAcquisitionLockRecord:
        created = _STALE_LOCK_INSPECTION_AT - timedelta(hours=2)
        return AuthAcquisitionLockRecord(
            provider_kind=AuthProviderKind.CLAVE_MOVIL,
            profile_name="operator",
            pid=os.getpid(),
            hostname=socket.gethostname(),
            created_at=created,
            expires_at=created + timedelta(seconds=1),
            operation="auth-login",
        )

    def _live_record(self) -> AuthAcquisitionLockRecord:
        now = datetime.now(UTC)
        return AuthAcquisitionLockRecord(
            provider_kind=AuthProviderKind.CLAVE_MOVIL,
            profile_name="operator",
            pid=os.getpid(),
            hostname=socket.gethostname(),
            created_at=now,
            expires_at=now + timedelta(hours=1),
            operation="auth-login",
        )

    def _write(self, path: pathlib.Path, record: AuthAcquisitionLockRecord) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(record.model_dump_json(indent=2), encoding=UTF_8_ENCODING)

    def test_removal_is_bound_to_the_inspected_bytes(self, tmp_path: pathlib.Path) -> None:
        """The compare-and-delete primitive refuses to unlink changed content.

        This is the intra-operation window the removal paths now close: the
        verdict is formed from one read, and the unlink is authorised only
        while the file still holds exactly those bytes.
        """
        path = tmp_path / "clave.lock"
        stale = self._expired_record().model_dump_json(indent=2)
        path.write_text(stale, encoding=UTF_8_ENCODING)
        live = self._live_record().model_dump_json(indent=2)
        path.write_text(live, encoding=UTF_8_ENCODING)

        removed = _remove_lock_file_if_unchanged(path, stale)

        assert removed is False
        assert path.read_text(encoding=UTF_8_ENCODING) == live

    def test_unchanged_bytes_are_removed(self, tmp_path: pathlib.Path) -> None:
        """Anti-tautology: the primitive discriminates rather than never deleting."""
        path = tmp_path / "clave.lock"
        stale = self._expired_record().model_dump_json(indent=2)
        path.write_text(stale, encoding=UTF_8_ENCODING)

        assert _remove_lock_file_if_unchanged(path, stale) is True
        assert not path.exists()

    def test_an_already_absent_file_counts_as_removed(self, tmp_path: pathlib.Path) -> None:
        assert _remove_lock_file_if_unchanged(tmp_path / "missing.lock", "anything") is True

    def test_a_corrupt_record_replaced_by_a_live_one_is_not_deleted(self, tmp_path: pathlib.Path) -> None:
        """A corrupt verdict does not authorise deleting a later valid record."""
        path = tmp_path / "clave.lock"
        path.write_text("{not json", encoding=UTF_8_ENCODING)
        live = self._live_record().model_dump_json(indent=2)
        path.write_text(live, encoding=UTF_8_ENCODING)

        assert _remove_lock_file_if_unchanged(path, "{not json") is False
        assert path.read_text(encoding=UTF_8_ENCODING) == live

    def test_reacquisition_leaves_a_replacement_lock_in_place(self, tmp_path: pathlib.Path) -> None:
        """The same window exists on the automatic recoverable-reacquire path."""
        settings = _settings(tmp_path)
        path = auth_acquisition_lock_path(settings, AuthProviderKind.CLAVE_MOVIL)
        self._write(path, self._expired_record())
        replacement = self._live_record()
        self._write(path, replacement)

        with (
            pytest.raises(AuthAcquisitionLockedError),
            acquire_auth_acquisition_lock(settings, AuthProviderKind.CLAVE_MOVIL, ttl_seconds=60),
        ):
            pytest.fail("a live replacement lock must block acquisition")

        assert path.exists()
        assert AuthAcquisitionLockRecord.model_validate_json(
            path.read_text(encoding=UTF_8_ENCODING),
        ) == replacement

    def test_an_unreplaced_stale_lock_is_still_cleared(self, tmp_path: pathlib.Path) -> None:
        """Anti-tautology: the guard discriminates rather than never deleting."""
        settings = _settings(tmp_path)
        path = auth_acquisition_lock_path(settings, AuthProviderKind.CLAVE_MOVIL)
        self._write(path, self._expired_record())

        result = clear_auth_acquisition_lock(settings, AuthProviderKind.CLAVE_MOVIL)

        assert not path.exists()
        assert result.state is AuthAcquisitionLockState.STALE

    def test_an_unreplaced_stale_lock_is_still_reacquired(self, tmp_path: pathlib.Path) -> None:
        settings = _settings(tmp_path)
        path = auth_acquisition_lock_path(settings, AuthProviderKind.CLAVE_MOVIL)
        self._write(path, self._expired_record())

        with acquire_auth_acquisition_lock(
            settings,
            AuthProviderKind.CLAVE_MOVIL,
            ttl_seconds=60,
        ) as record:
            assert record.operation == "auth-login"
            assert path.exists()
