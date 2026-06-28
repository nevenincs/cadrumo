"""Tests for crash-recoverable auth acquisition locks."""

from __future__ import annotations

import os
import socket
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ....core.config import Settings
from ....core.external_constants import UTF_8_ENCODING
from .. import AuthProviderKind
from .._acquisition_lock import (
    AuthAcquisitionLockedError,
    AuthAcquisitionLockRecord,
    AuthAcquisitionLockState,
    acquire_auth_acquisition_lock,
    auth_acquisition_lock_path,
    clear_auth_acquisition_lock,
    inspect_auth_acquisition_lock,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _active_profile() -> Iterator[None]:
    from ....core.config import override_settings

    with override_settings(aeat_active_profile="operator"):
        yield


def _settings(tmp_path: Path) -> Settings:
    """Build a validated Settings instance with the tokens dir pinned.

    Direct constructor kwargs route through the pydantic validator chain;
    the previous ``model_copy(update=)`` form bypassed validators per
    pydantic v2 semantics.
    """
    return Settings(aeat_token_dir=tmp_path / "tokens")


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
    now = datetime.now(UTC)
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
