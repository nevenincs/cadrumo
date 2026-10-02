"""Unit contracts for remote failures versus failed local effects and cleanup."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal, Never, cast, override

import pytest

from cadrumo.application.auth.certificate_secret_backend import CertificateSecretBackendFactory
from cadrumo.application.auth.operator_scope_ports import OperatorScopePorts
from cadrumo.application.auth.protocols import BrowserSessionFactoryPort
from cadrumo.application.auth.session_types import AeatSession, CertificateSessionDetail
from cadrumo.application.live import notifications
from cadrumo.application.live.filed_data_capture import (
    _capture_filed_history_iva_wallet,
    _capture_filed_history_notifications,
)
from cadrumo.application.live.filed_data_ports import FiledEffectGuard
from cadrumo.application.live.notification_ports import NotificationsPorts, NotificationsSnapshot
from cadrumo.application.live.remote_state_models import IvaWalletCaptureReport
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, close_async_resources
from cadrumo.core.config import Settings, override_settings
from cadrumo.core.period import Period

from .filed_observation_test_support import _UnavailableIvaRemoteStatePort

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 10, 2, tzinfo=UTC)
_PROFILE_ID = "00000000-0000-4000-8000-000000000001"
type _Stage = Literal["iva", "notifications"]


def _session() -> AeatSession:
    return AeatSession(
        authenticated_at=_NOW,
        idle_deadline=_NOW + timedelta(minutes=5),
        storage_state_path=None,
        identity_nif="12345678Z",
        provider_detail=CertificateSessionDetail(
            certificate_thumbprint="synthetic-thumbprint", certificate_subject="synthetic subject"
        ),
    )


class _Guard:
    def __init__(self) -> None:
        self.entries = 0
        self.active = False

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[None]:
        assert not self.active
        self.entries += 1
        self.active = True
        try:
            yield
        finally:
            self.active = False


class _IvaPort(_UnavailableIvaRemoteStatePort):
    def __init__(self, failure: BaseException, *, local: bool, guard: _Guard) -> None:
        self.failure = failure
        self.local = local
        self.guard = guard
        self.captures = 0

    @override
    async def active_verified_session(
        self, *, operation: str, target_url: str | None, **_kwargs: object
    ) -> tuple[AeatSession, Settings]:
        assert operation == "live-iva-wallet-read"
        assert target_url == self.wallet_target_url
        return _session(), Settings()

    @override
    async def capture_wallet(
        self,
        session: AeatSession,
        *,
        settings: Settings,
        target_year: int,
        target_period: Period,
        taxpayer_nif: str | None,
        output_root: Path | None,
        progress_context: dict[str, object] | None,
        effect_guard: FiledEffectGuard | None = None,
        **_kwargs: object,
    ) -> IvaWalletCaptureReport:
        del settings, taxpayer_nif, progress_context
        assert session.identity_nif == "12345678Z"
        assert target_year == 2026 and target_period == Period.from_year_and_code(2026, "1T")
        assert output_root is not None
        assert not self.guard.active
        self.captures += 1
        if self.local:
            assert effect_guard is not None
            async with effect_guard():
                assert self.guard.active
                raise self.failure
        raise self.failure


class _Query:
    def __init__(self, failure: BaseException, *, local: bool) -> None:
        self.failure = failure
        self.local = local
        self.calls = 0

    async def fetch(self, session: AeatSession, *, settings: Settings) -> NotificationsSnapshot:
        del settings
        assert session.identity_nif == "12345678Z"
        self.calls += 1
        if not self.local:
            raise self.failure
        return NotificationsSnapshot(rows=(), captured_at=_NOW, source_url="https://test.invalid/notifications")


async def _stage(
    stage: _Stage, failure: BaseException, *, local: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[str, _Guard]:
    guard = _Guard()
    if stage == "iva":
        port = _IvaPort(failure, local=local, guard=guard)
        result = await _capture_filed_history_iva_wallet(
            iva_remote_state_port=port,
            resolved_today=date(2026, 10, 2),
            output_root=tmp_path,
            effect_guard=guard,
        )
        assert port.captures == 1
    else:
        # Replace only external authentication; the stage, query and local
        # NotificationsService persistence orchestration remain real.
        async def authenticated(**_kwargs: object) -> tuple[AeatSession, Settings]:
            return _session(), Settings()

        monkeypatch.setattr(notifications, "active_verified_session", authenticated)
        query = _Query(failure, local=local)

        def repository(bucket_id: str) -> Never:
            assert bucket_id == _PROFILE_ID
            assert guard.active
            raise failure

        with override_settings(cadrumo_active_profile=_PROFILE_ID):
            result = await _capture_filed_history_notifications(
                certificate_secret_backend_factory=cast(CertificateSecretBackendFactory, object()),
                browser_session_factory=cast(BrowserSessionFactoryPort, object()),
                operator_scope_ports=cast(OperatorScopePorts, object()),
                notifications_ports=NotificationsPorts(snapshot_query=query, snapshot_repository_factory=repository),
                effect_guard=guard,
            )
        assert query.calls == 1
    assert not guard.active
    return result.status, guard


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["iva", "notifications"])
async def test_remote_failure_remains_an_independent_failed_stage(
    stage: _Stage, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    status, guard = await _stage(
        stage, OSError("synthetic remote failure"), local=False, monkeypatch=monkeypatch, tmp_path=tmp_path
    )
    assert status == "failed"
    assert guard.entries == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["iva", "notifications"])
async def test_failure_inside_local_effect_guard_propagates_exact_error(
    stage: _Stage, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    failure = OSError("synthetic local persistence failure")
    with pytest.raises(OSError) as caught:
        await _stage(stage, failure, local=True, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert caught.value is failure


class _Release:
    def __init__(self) -> None:
        self.calls = 0
        self.released = False

    async def close(self) -> None:
        self.calls += 1
        if self.calls == 1:
            raise OSError("synthetic resource release failure")
        self.released = True


@pytest.mark.asyncio
async def test_iva_failure_after_successful_local_write_propagates_exact_error(tmp_path: Path) -> None:
    failure = OSError("synthetic reread failure after local mutation")
    guard = _Guard()
    mutations: list[str] = []

    class _RereadFailurePort(_IvaPort):
        @override
        async def capture_wallet(self, session: AeatSession, **kwargs: object) -> IvaWalletCaptureReport:
            assert session.identity_nif == "12345678Z"
            effect_guard = cast(FiledEffectGuard, kwargs["effect_guard"])
            async with effect_guard():
                assert guard.active
                mutations.append("persisted")
            assert not guard.active
            raise failure

    port = _RereadFailurePort(failure, local=True, guard=guard)
    with pytest.raises(OSError) as caught:
        await _capture_filed_history_iva_wallet(
            iva_remote_state_port=port,
            resolved_today=date(2026, 10, 2),
            output_root=tmp_path,
            effect_guard=guard,
        )
    assert caught.value is failure
    assert mutations == ["persisted"]
    assert guard.entries == 1 and not guard.active


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["iva", "notifications"])
@pytest.mark.parametrize("attached", [False, True])
async def test_failed_cleanup_propagates_with_actual_retry_owner(
    stage: _Stage, attached: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    resource = _Release()
    if attached:
        failure: BaseException = OSError("synthetic remote failure with failed cleanup")
        await close_async_resources(resource, task_name="stage-cleanup", close_attempts=1, primary_error=failure)
        cleanup = failure.__dict__["async_cleanup_error"]
        assert isinstance(cleanup, AsyncResourceCleanupError)
    else:
        with pytest.raises(AsyncResourceCleanupError) as caught:
            await close_async_resources(resource, task_name="stage-cleanup", close_attempts=1, primary_error=None)
        cleanup = caught.value
        failure = cleanup
    assert cleanup.resources == (resource,)
    assert resource.calls == 1 and not resource.released
    with pytest.raises(type(failure)) as escaped:
        await _stage(stage, failure, local=False, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert escaped.value is failure
    assert cleanup.resources == (resource,)
    await cleanup.retry_cleanup()
    assert resource.calls == 2 and resource.released
