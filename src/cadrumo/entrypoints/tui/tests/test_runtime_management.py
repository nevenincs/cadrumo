"""A passive TUI status panel keeps readiness separate from manager policy."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from pathlib import Path
from threading import Event, get_ident
from uuid import uuid4

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, Static

from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.management import (
    RuntimeManagerInspection,
    RuntimeManagerKind,
    RuntimeManagerProcessState,
)
from cadrumo.application.runtime.management_status import (
    RuntimeListenerState,
    RuntimeManagementSnapshot,
    RuntimeManagerAvailability,
)
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, async_cleanup_failures, close_async_resources
from cadrumo.core.config import override_settings
from cadrumo.core.i18n.render import tr
from cadrumo.entrypoints.tests.test_runtime_management import StopFixture

from ..app import CadrumoTuiApp
from ..components.host import ScreenHostApp
from ..runtime_management import RuntimeManagementCleanup, RuntimeManagementScreen, RuntimeStopConfirmationScreen

pytestmark = [pytest.mark.hex_entrypoint]


async def _until[T](pilot: Pilot[T], condition: Callable[[], bool]) -> None:
    async with asyncio.timeout(5):
        while not condition():
            await pilot.pause(0.02)


def _available() -> RuntimeManagementSnapshot:
    return RuntimeManagementSnapshot(
        listener=RuntimeListenerState.READY,
        manager_availability=RuntimeManagerAvailability.AVAILABLE,
        manager=RuntimeManagerInspection(
            kind=RuntimeManagerKind.WINDOWS_TASK,
            available=True,
            provisioned=True,
            binding_matches=False,
            login_autostart=False,
            process_state=RuntimeManagerProcessState.STOPPED,
        ),
    )


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["accepted", "lost"])
async def test_stop_acceptance_or_unknown_dispatch_stays_fenced_after_refresh(
    monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    fixture = StopFixture(outcome="lost" if outcome == "lost" else "accepted")
    previews = 0

    async def preview() -> object:
        nonlocal previews
        previews += 1
        return fixture.consent

    async def read() -> RuntimeManagementSnapshot:
        return _available()

    monkeypatch.setattr("cadrumo.entrypoints.tui.runtime_management.preview_installed_runtime_stop", preview)
    cleanup = RuntimeManagementCleanup()
    screen = RuntimeManagementScreen(reader=read, cleanup=cleanup)
    app = ScreenHostApp(screen)
    async with app.run_test(size=(100, 30)) as pilot:
        await _until(
            pilot,
            lambda: (
                not screen._busy
                and tr("tui.runtime_management.listener.ready")
                in str(screen.query_one("#runtime-management-listener", Static).content)
            ),
        )
        screen.query_one("#runtime-management-stop", Button).press()
        await _until(
            pilot,
            lambda: (
                isinstance(app.screen, RuntimeStopConfirmationScreen)
                and bool(app.screen.query("#runtime-stop-confirm"))
            ),
        )
        app.screen.query_one("#runtime-stop-confirm", Button).press()
        await _until(pilot, lambda: not screen._busy and fixture.consent.released)
        message = str(screen.query_one("#runtime-management-status", Static).content)
        expected_key = (
            "tui.runtime_management.stop_accepted"
            if outcome == "accepted"
            else "tui.runtime_management.availability.unknown"
        )
        assert tr(expected_key) in message
        assert tr("tui.runtime_management.refused") not in message
        assert screen.query_one("#runtime-management-stop", Button).disabled
        screen.query_one("#runtime-management-refresh", Button).press()
        await _until(
            pilot,
            lambda: (
                not screen._busy
                and tr("tui.runtime_management.listener.ready")
                in str(screen.query_one("#runtime-management-listener", Static).content)
            ),
        )
        assert screen.query_one("#runtime-management-stop", Button).disabled
        assert tr(expected_key) in str(screen.query_one("#runtime-management-status", Static).content)
        await screen._stop()
        screen._stop_pressed()
        assert previews == 1 and fixture.channel.confirmations == 1
        assert (fixture.consent.accepted is not None) == (outcome == "accepted")
    reopened = RuntimeManagementScreen(reader=read, cleanup=cleanup)
    async with ScreenHostApp(reopened).run_test(size=(100, 30)) as pilot:
        await _until(
            pilot,
            lambda: (
                not reopened._busy
                and tr("tui.runtime_management.listener.ready")
                in str(reopened.query_one("#runtime-management-listener", Static).content)
            ),
        )
        assert reopened.query_one("#runtime-management-stop", Button).disabled
        assert tr(expected_key) in str(reopened.query_one("#runtime-management-status", Static).content)
        await reopened._stop()
        reopened._stop_pressed()
        assert previews == 1 and fixture.channel.confirmations == 1
        assert cleanup.consent is fixture.consent


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancelled_stop_preview_can_be_discarded_without_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = StopFixture()
    monkeypatch.setattr("cadrumo.entrypoints.tui.runtime_management.preview_installed_runtime_stop", fixture.open)

    async def read() -> RuntimeManagementSnapshot:
        return _available()

    screen = RuntimeManagementScreen(reader=read)
    app = ScreenHostApp(screen)
    async with app.run_test(size=(100, 30)) as pilot:
        await _until(
            pilot,
            lambda: (
                not screen._busy
                and tr("tui.runtime_management.listener.ready")
                in str(screen.query_one("#runtime-management-listener", Static).content)
            ),
        )
        screen.query_one("#runtime-management-stop", Button).press()
        await _until(
            pilot,
            lambda: (
                isinstance(app.screen, RuntimeStopConfirmationScreen)
                and bool(app.screen.query("#runtime-stop-confirm"))
            ),
        )
        app.screen.query_one("#runtime-stop-cancel", Button).press()
        await _until(pilot, lambda: not screen._busy and fixture.consent.released)
        assert not screen.query_one("#runtime-management-stop", Button).disabled
        assert fixture.channel.confirmations == 0 and not fixture.consent.confirmation_started


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_ack_cleanup_failure_is_visible_and_retained_after_screen_closure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = StopFixture(channel_failures=3)
    monkeypatch.setattr("cadrumo.entrypoints.tui.runtime_management.preview_installed_runtime_stop", fixture.open)

    async def read() -> RuntimeManagementSnapshot:
        return _available()

    cleanup = RuntimeManagementCleanup()
    screen = RuntimeManagementScreen(reader=read, cleanup=cleanup)
    app = ScreenHostApp(screen)
    async with app.run_test(size=(100, 30)) as pilot:
        await _until(
            pilot,
            lambda: (
                not screen._busy
                and tr("tui.runtime_management.listener.ready")
                in str(screen.query_one("#runtime-management-listener", Static).content)
            ),
        )
        screen.query_one("#runtime-management-stop", Button).press()
        await _until(
            pilot,
            lambda: (
                isinstance(app.screen, RuntimeStopConfirmationScreen)
                and bool(app.screen.query("#runtime-stop-confirm"))
            ),
        )
        app.screen.query_one("#runtime-stop-confirm", Button).press()
        await _until(pilot, lambda: not screen._busy and fixture.channel.close_calls == 1)
        message = str(screen.query_one("#runtime-management-status", Static).content)
        assert tr("tui.runtime_management.stop_accepted") in message
        assert tr("tui.runtime_management.availability.unavailable") in message
        assert "synthetic private" not in message
        assert screen.query_one("#runtime-management-stop", Button).disabled
        assert fixture.consent.accepted is not None
        assert fixture.endpoint.close_calls == 1
    assert fixture.channel.close_calls == 2 and cleanup.pending
    with pytest.raises(AsyncResourceCleanupError) as failed:
        await cleanup.release()
    assert failed.value is cleanup.failure and fixture.channel.close_calls == 3
    await failed.value.retry_cleanup()
    assert fixture.channel.close_calls == 4 and fixture.endpoint.close_calls == 1
    assert not cleanup.pending
    assert fixture.consent.released and fixture.channel.confirmations == 1
    with pytest.raises(RuntimeRefusalError) as refused:
        await fixture.consent.confirm()
    assert refused.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_collector_preserves_original_cancellation_and_one_native_retry_authority() -> None:
    fixture = StopFixture(channel_failures=2)
    fixture.channel.continue_reply.clear()
    cleanup = RuntimeManagementCleanup()
    cleanup.retain_consent(fixture.consent)
    confirming = asyncio.create_task(fixture.consent.confirm())
    try:
        assert await asyncio.to_thread(fixture.channel.confirming.wait, 2)
        confirming.cancel("original-screen-stop-cancellation")
        fixture.channel.continue_reply.set()
        with pytest.raises(asyncio.CancelledError) as cancelled:
            await confirming
        primary = cancelled.value
        with pytest.raises(asyncio.CancelledError) as releasing:
            await fixture.consent.release(primary_error=primary)
        assert releasing.value is primary
        cleanup.retain(primary)
        assert cleanup.pending and cleanup.failure is primary
        with pytest.raises(asyncio.CancelledError) as retry_failed:
            await cleanup.release()
        assert retry_failed.value is primary
        assert fixture.channel.close_calls == 2 and fixture.endpoint.close_calls == 1
        retained = primary.__dict__.get("async_cleanup_error")
        assert isinstance(retained, AsyncResourceCleanupError)
        await retained.retry_cleanup()
        assert fixture.channel.close_calls == 3 and fixture.endpoint.close_calls == 1
        assert not cleanup.pending and fixture.consent.released
        await cleanup.release()
        assert fixture.channel.close_calls == 3 and fixture.channel.confirmations == 1
    finally:
        fixture.channel.continue_reply.set()
        if not confirming.done():
            await confirming


class _AsyncRelease:
    """A non-native actual owner whose successful release cannot be repeated."""

    def __init__(self, *, failures: int) -> None:
        self.failures = failures
        self.calls = 0
        self.closed = False

    async def close(self) -> None:
        assert not self.closed, "a historical attachment replayed successful release"
        self.calls += 1
        if self.calls <= self.failures:
            raise OSError("synthetic asynchronous release failure")
        self.closed = True


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("cancelled", [False, True], ids=["body-error", "original-cancellation"])
async def test_stop_collector_retires_success_despite_historical_primary_cleanup(cancelled: bool) -> None:
    resource = _AsyncRelease(failures=1)
    primary = asyncio.CancelledError("original-body-cancellation") if cancelled else ValueError("original-body-error")
    if cancelled:
        with pytest.raises(asyncio.CancelledError) as caught:
            await close_async_resources(resource, task_name="historical-owner-close", primary_error=primary)
        assert caught.value is primary
    else:
        await close_async_resources(resource, task_name="historical-owner-close", primary_error=primary)
    assert resource.calls == 1 and not resource.closed
    cleanup = RuntimeManagementCleanup()
    cleanup.retain(primary)
    assert cleanup.pending and cleanup.failure is primary
    for _ in range(2):
        if cancelled:
            with pytest.raises(asyncio.CancelledError) as caught:
                await cleanup.release(primary_error=primary)
            assert caught.value is primary
        else:
            await cleanup.release(primary_error=primary)
        assert resource.closed and resource.calls == 2
        assert not cleanup.pending and cleanup.failure is primary
    # Explicitly re-adopting the old canonical error cannot resurrect its
    # owner after this scope has witnessed that exact owner release succeed.
    cleanup.retain(primary)
    assert not cleanup.pending
    await cleanup.release()
    assert resource.calls == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_collector_retains_only_current_failed_owners_under_original_primary() -> None:
    first, second = _AsyncRelease(failures=1), _AsyncRelease(failures=2)
    primary = ValueError("original-body-error")
    await close_async_resources(first, second, task_name="historical-owner-close", primary_error=primary)
    cleanup = RuntimeManagementCleanup()
    cleanup.retain(primary)
    await cleanup.release(primary_error=primary)
    assert first.closed and first.calls == 2
    assert not second.closed and second.calls == 2
    assert cleanup.pending and cleanup.failure is primary
    await cleanup.release(primary_error=primary)
    assert second.closed and second.calls == 3
    assert first.calls == 2 and not cleanup.pending
    await cleanup.release(primary_error=primary)
    assert first.calls == 2 and second.calls == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_passive_snapshot_shows_independent_axes_and_refreshes_once() -> None:
    observations = [
        _available(),
        RuntimeManagementSnapshot(
            listener=RuntimeListenerState.UNAVAILABLE,
            manager_availability=RuntimeManagerAvailability.UNSUPPORTED,
        ),
    ]
    calls = 0
    ui_thread = get_ident()

    async def read() -> RuntimeManagementSnapshot:
        nonlocal calls
        assert get_ident() != ui_thread
        result = observations[calls]
        calls += 1
        return result

    screen = RuntimeManagementScreen(reader=read)
    async with ScreenHostApp(screen).run_test(size=(100, 30)) as pilot:
        await _until(pilot, lambda: calls == 1 and not screen._busy)
        assert tr("tui.runtime_management.listener.ready") in str(
            screen.query_one("#runtime-management-listener", Static).content
        )
        assert tr("tui.runtime_management.availability.available") in str(
            screen.query_one("#runtime-management-manager-availability", Static).content
        )
        assert tr("flows.confirm.yes") in str(screen.query_one("#runtime-management-provisioned", Static).content)
        assert tr("flows.confirm.no") in str(screen.query_one("#runtime-management-binding", Static).content)
        assert tr("tui.runtime_management.process.stopped") in str(
            screen.query_one("#runtime-management-process", Static).content
        )
        assert not screen.query("Input")
        screen.query_one("#runtime-management-refresh", Button).press()
        await _until(pilot, lambda: calls == 2 and not screen._busy)
        assert tr("tui.runtime_management.listener.unavailable") in str(
            screen.query_one("#runtime-management-listener", Static).content
        )
        assert tr("tui.runtime_management.availability.unsupported") in str(
            screen.query_one("#runtime-management-manager-availability", Static).content
        )
        assert tr("tui.runtime_management.not_reported") in str(
            screen.query_one("#runtime-management-process", Static).content
        )
        assert calls == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_close_owns_pending_read_and_never_restores_late_snapshot() -> None:
    started, release, completed = Event(), Event(), Event()
    calls = 0

    async def read() -> RuntimeManagementSnapshot:
        nonlocal calls
        calls += 1
        started.set()
        await asyncio.to_thread(release.wait)
        completed.set()
        return _available()

    app = CadrumoTuiApp(runtime_management_reader=read)
    async with app.run_test(size=(100, 30)) as pilot:
        app.action_runtime_management()
        await _until(pilot, lambda: isinstance(app.screen, RuntimeManagementScreen))
        screen = app.screen
        assert isinstance(screen, RuntimeManagementScreen)
        assert await asyncio.to_thread(started.wait, 3)
        assert screen.query_one("#runtime-management-refresh", Button).disabled
        screen.query_one("#runtime-management-refresh", Button).press()
        await pilot.pause(0.02)
        assert calls == 1
        screen.query_one("#runtime-management-close", Button).press()
        release.set()
        assert await asyncio.to_thread(completed.wait, 3)
        await _until(pilot, lambda: not isinstance(app.screen, RuntimeManagementScreen))
        assert calls == 1
        assert not screen._live


@pytest.mark.unit
@pytest.mark.asyncio
async def test_close_before_queued_refresh_enters_never_starts_another_read() -> None:
    calls = 0

    async def read() -> RuntimeManagementSnapshot:
        nonlocal calls
        calls += 1
        return _available()

    app = CadrumoTuiApp(runtime_management_reader=read)
    async with app.run_test(size=(100, 30)) as pilot:
        app.action_runtime_management()
        await _until(pilot, lambda: isinstance(app.screen, RuntimeManagementScreen) and calls == 1)
        screen = app.screen
        assert isinstance(screen, RuntimeManagementScreen)
        await _until(pilot, lambda: not screen._busy)
        screen._start_refresh()
        assert screen._busy
        screen.action_close()
        await _until(pilot, lambda: not isinstance(app.screen, RuntimeManagementScreen))
        await pilot.pause(0.02)
        assert calls == 1
        assert not screen._live


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_refresh_clears_stale_manager_facts() -> None:
    calls = 0

    async def read() -> RuntimeManagementSnapshot:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic private path must not surface")
        return _available()

    screen = RuntimeManagementScreen(reader=read)
    async with ScreenHostApp(screen).run_test(size=(100, 30)) as pilot:
        await _until(pilot, lambda: calls == 1 and not screen._busy)
        screen.query_one("#runtime-management-refresh", Button).press()
        await _until(pilot, lambda: calls == 2 and not screen._busy)
        assert tr("tui.runtime_management.refused") in str(
            screen.query_one("#runtime-management-status", Static).content
        )
        assert tr("tui.runtime_management.not_reported") in str(
            screen.query_one("#runtime-management-provisioned", Static).content
        )
        assert "synthetic private path" not in str(screen.query_one("#runtime-management-status", Static).content)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_human_root_offers_profile_free_status_as_a_system_command() -> None:
    calls = 0

    async def read() -> RuntimeManagementSnapshot:
        nonlocal calls
        calls += 1
        return RuntimeManagementSnapshot(
            listener=RuntimeListenerState.UNKNOWN,
            manager_availability=RuntimeManagerAvailability.UNKNOWN,
        )

    app = CadrumoTuiApp(runtime_management_reader=read)
    async with app.run_test(size=(100, 30)) as pilot:
        assert tr("tui.runtime_management.open") in {item.title for item in app.get_system_commands(app.screen)}
        app.action_runtime_management()
        await _until(pilot, lambda: isinstance(app.screen, RuntimeManagementScreen) and calls == 1)
        assert isinstance(app.screen, RuntimeManagementScreen)
        app.screen.action_close()
        await _until(pilot, lambda: not isinstance(app.screen, RuntimeManagementScreen))


@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows owner-only pipes")
@pytest.mark.asyncio
async def test_installed_tui_passively_observes_existing_native_listener(tmp_path: Path) -> None:
    """The default UI reader uses the real peer-verified status path without login."""
    root = tmp_path / f"tui-management-{uuid4()}"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    stop = Event()
    server = RuntimeTransportServer(endpoint, product_version=version("cadrumo"), stop=stop)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool, override_settings(cadrumo_local_storage_root=root):
            running = pool.submit(server.serve)
            try:
                assert await asyncio.to_thread(server.ready.wait, 3)
                screen = RuntimeManagementScreen()
                async with ScreenHostApp(screen).run_test(size=(100, 30)) as pilot:
                    await _until(
                        pilot,
                        lambda: (
                            tr("tui.runtime_management.listener.ready")
                            in str(screen.query_one("#runtime-management-listener", Static).content)
                            and not screen._busy
                        ),
                    )
                    availability = str(screen.query_one("#runtime-management-manager-availability", Static).content)
                    assert any(
                        tr(key) in availability
                        for key in (
                            "tui.runtime_management.availability.available",
                            "tui.runtime_management.availability.unavailable",
                        )
                    )
                    assert not screen.query("Input")
                    assert not stop.is_set()
            finally:
                stop.set()
                await asyncio.to_thread(running.result, 10)
    finally:
        endpoint.close()


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("primary_kind", ["aggregate", "value-error", "cancellation"])
async def test_stop_collector_public_retry_contains_only_current_failed_owner(primary_kind: str) -> None:
    """A completed owner is absent from the canonical error's public retry route."""
    first, second = _AsyncRelease(failures=1), _AsyncRelease(failures=2)
    primary: BaseException | None = None
    if primary_kind == "value-error":
        primary = ValueError("original-body-error")
    elif primary_kind == "cancellation":
        primary = asyncio.CancelledError("original-body-cancellation")
    if primary is None:
        with pytest.raises(AsyncResourceCleanupError) as original:
            await close_async_resources(first, second, task_name="original-two-owner-close", primary_error=None)
        original_error: BaseException = original.value
    elif isinstance(primary, asyncio.CancelledError):
        with pytest.raises(asyncio.CancelledError) as original_cancel:
            await close_async_resources(first, second, task_name="original-two-owner-close", primary_error=primary)
        assert original_cancel.value is primary
        original_error = primary
    else:
        await close_async_resources(first, second, task_name="original-two-owner-close", primary_error=primary)
        original_error = primary
    cleanup = RuntimeManagementCleanup()
    cleanup.retain(original_error)
    if primary is None:
        with pytest.raises(AsyncResourceCleanupError) as current:
            await cleanup.release()
        retained = current.value
    elif isinstance(primary, asyncio.CancelledError):
        with pytest.raises(asyncio.CancelledError) as current_cancel:
            await cleanup.release(primary_error=primary)
        assert current_cancel.value is primary
        retained = primary.__dict__.get("cleanup_error")
        assert retained is primary.__dict__.get("async_cleanup_error")
    else:
        await cleanup.release(primary_error=primary)
        assert cleanup.failure is primary
        retained = primary.__dict__.get("async_cleanup_error")
    assert first.closed and first.calls == 2
    assert not second.closed and second.calls == 2
    assert isinstance(retained, AsyncResourceCleanupError)
    assert retained.resources == (second,)
    await retained.retry_cleanup()
    assert second.closed and second.calls == 3
    assert first.calls == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_collector_fresh_cancellation_retains_body_and_current_failed_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancellation during actual release keeps the older body and the retry owner."""
    resource = _AsyncRelease(failures=2)
    primary = ValueError("original-body-error")
    await close_async_resources(resource, task_name="original-owner-close", primary_error=primary)
    cleanup = RuntimeManagementCleanup()
    cleanup.retain(primary)
    started, proceed = asyncio.Event(), asyncio.Event()
    close = resource.close

    async def blocked_close() -> None:
        started.set()
        await proceed.wait()
        await close()

    monkeypatch.setattr(resource, "close", blocked_close)
    task = asyncio.create_task(cleanup.release(primary_error=primary))
    try:
        async with asyncio.timeout(5):
            await started.wait()
            task.cancel("fresh-cleanup-cancellation")
            proceed.set()
            with pytest.raises(asyncio.CancelledError) as cancelled:
                await task
        assert cancelled.value.args == ("fresh-cleanup-cancellation",)
        assert cancelled.value.__dict__.get("body_error") is primary
        assert cleanup.failure is cancelled.value
        retained = cancelled.value.__dict__.get("cleanup_error")
        assert isinstance(retained, AsyncResourceCleanupError)
        assert retained.resources == (resource,)
        assert retained is cancelled.value.__dict__.get("async_cleanup_error")
        assert resource.calls == 2 and not resource.closed
        await retained.retry_cleanup()
        assert resource.closed and resource.calls == 3
    finally:
        proceed.set()
        if not task.done():
            await task


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("second_failures", [2, 1], ids=["partial-release", "complete-release"])
async def test_stop_collector_explicit_aggregate_primary_public_retry_discards_released_owners(
    second_failures: int,
) -> None:
    """The original aggregate survives unwinding with only its still-owned resources."""
    first, second = _AsyncRelease(failures=1), _AsyncRelease(failures=second_failures)
    with pytest.raises(AsyncResourceCleanupError) as original:
        await close_async_resources(first, second, task_name="original-aggregate-close", primary_error=None)
    primary = original.value
    assert primary.resources == (first, second)
    cleanup = RuntimeManagementCleanup()
    cleanup.retain(primary)
    with pytest.raises(AsyncResourceCleanupError) as unwound:
        try:
            raise primary
        finally:
            await cleanup.release(primary_error=primary)
    assert unwound.value is primary
    assert first.closed and first.calls == 2
    assert second.calls == 2
    assert primary.resources == ((second,) if second_failures == 2 else ())
    await primary.retry_cleanup()
    assert first.calls == 2 and second.closed
    assert second.calls == (3 if second_failures == 2 else 2)


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["refusal", "native-cancellation", "caller-cancellation"])
async def test_start_refresh_retains_exact_primary_and_actual_cleanup_beyond_screen(
    mode: str,
) -> None:
    resource = _AsyncRelease(failures=2)
    primary = (
        asyncio.CancelledError("native-management-action-cancellation")
        if mode == "native-cancellation"
        else RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    )
    entered = Event()
    proceed = Event()
    if mode != "caller-cancellation":
        proceed.set()
    cleanup = RuntimeManagementCleanup()
    calls = 0

    async def read() -> RuntimeManagementSnapshot:
        return _available()

    async def start() -> RuntimeManagementSnapshot:
        nonlocal calls
        calls += 1
        entered.set()
        assert await asyncio.to_thread(proceed.wait, 3)
        await close_async_resources(resource, task_name="management-action-fault", primary_error=primary)
        raise primary

    screen = RuntimeManagementScreen(reader=read, starter=start, cleanup=cleanup)
    app = ScreenHostApp(screen)
    refreshing: asyncio.Task[None] | None = None
    try:
        async with app.run_test(size=(100, 30)) as pilot:
            await _until(pilot, lambda: not screen._busy and screen.is_mounted)
            if mode == "caller-cancellation":
                refreshing = asyncio.create_task(screen._refresh(start))
                assert await asyncio.to_thread(entered.wait, 2)
                refreshing.cancel("caller-management-action-cancellation")
                await asyncio.sleep(0)
                assert not refreshing.done() and resource.calls == 0
                proceed.set()
                with pytest.raises(asyncio.CancelledError) as failed:
                    await refreshing
                assert failed.value.args == ("caller-management-action-cancellation",)
                assert cleanup.failure is failed.value
            else:
                screen.query_one("#runtime-management-start", Button).press()
                await _until(pilot, lambda: calls == 1 and not screen._busy)
                assert cleanup.failure is primary
            assert cleanup.pending and resource.calls == 1
            assert tr("tui.runtime_management.refused") in str(
                screen.query_one("#runtime-management-status", Static).content
            )
            assert "synthetic asynchronous release failure" not in str(
                screen.query_one("#runtime-management-status", Static).content
            )
        assert cleanup.pending and resource.calls == 1
        failure = cleanup.failure
        assert failure is not None
        retained = async_cleanup_failures(failure)
        assert retained and all(item.resources == (resource,) for item in retained)
        with pytest.raises(type(failure)) as retry_failed:
            await cleanup.release()
        assert retry_failed.value is failure and resource.calls == 2 and cleanup.pending
        try:
            await cleanup.release(primary_error=failure)
        except asyncio.CancelledError as cancellation:
            assert cancellation is failure
        assert resource.closed and resource.calls == 3 and not cleanup.pending
        await cleanup.release()
        assert resource.calls == 3 and calls == 1
    finally:
        proceed.set()
        if refreshing is not None and not refreshing.done():
            await refreshing
