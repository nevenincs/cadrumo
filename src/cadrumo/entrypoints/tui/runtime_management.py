"""Profile-free presentation and explicit control of the installed runtime."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import ClassVar, cast, override

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static
from textual.worker import Worker, WorkerCancelled, WorkerError, WorkerFailed

from ...adapters.local_runtime.framing import RuntimeTransportCleanup
from ...application.runtime.management import RuntimeManagerKind, RuntimeManagerProcessState
from ...application.runtime.management_status import (
    RuntimeListenerState,
    RuntimeManagementSnapshot,
    RuntimeManagerAvailability,
)
from ...core.async_cleanup import (
    AsyncCloseable,
    AsyncResourceCleanupError,
    await_cancellation_complete,
    close_async_resources,
)
from ...core.i18n.render import tr
from ..runtime_management import (
    RuntimeStopConsent,
    configure_installed_runtime_management,
    inspect_installed_runtime_management,
    preview_installed_runtime_stop,
    start_installed_runtime_management,
)

type RuntimeManagementReader = Callable[[], Awaitable[RuntimeManagementSnapshot]]
type RuntimeManagementAction = Callable[[], Awaitable[object]]

_LISTENER_TEXT: dict[RuntimeListenerState, Callable[[], str]] = {
    RuntimeListenerState.READY: lambda: tr("tui.runtime_management.listener.ready"),
    RuntimeListenerState.DRAINING: lambda: tr("tui.runtime_management.listener.draining"),
    RuntimeListenerState.UNAVAILABLE: lambda: tr("tui.runtime_management.listener.unavailable"),
    RuntimeListenerState.REFUSED: lambda: tr("tui.runtime_management.listener.refused"),
    RuntimeListenerState.UNKNOWN: lambda: tr("tui.runtime_management.listener.unknown"),
}
_AVAILABILITY_TEXT: dict[RuntimeManagerAvailability, Callable[[], str]] = {
    RuntimeManagerAvailability.AVAILABLE: lambda: tr("tui.runtime_management.availability.available"),
    RuntimeManagerAvailability.UNAVAILABLE: lambda: tr("tui.runtime_management.availability.unavailable"),
    RuntimeManagerAvailability.UNSUPPORTED: lambda: tr("tui.runtime_management.availability.unsupported"),
    RuntimeManagerAvailability.REFUSED: lambda: tr("tui.runtime_management.availability.refused"),
    RuntimeManagerAvailability.UNKNOWN: lambda: tr("tui.runtime_management.availability.unknown"),
}
_KIND_TEXT: dict[RuntimeManagerKind, Callable[[], str]] = {
    RuntimeManagerKind.WINDOWS_TASK: lambda: tr("tui.runtime_management.kind.windows_task"),
    RuntimeManagerKind.MACOS_AGENT: lambda: tr("tui.runtime_management.kind.macos_agent"),
    RuntimeManagerKind.LINUX_USER_SERVICE: lambda: tr("tui.runtime_management.kind.linux_user_service"),
}
_PROCESS_TEXT: dict[RuntimeManagerProcessState, Callable[[], str]] = {
    RuntimeManagerProcessState.STOPPED: lambda: tr("tui.runtime_management.process.stopped"),
    RuntimeManagerProcessState.STARTING: lambda: tr("tui.runtime_management.process.starting"),
    RuntimeManagerProcessState.RUNNING: lambda: tr("tui.runtime_management.process.running"),
    RuntimeManagerProcessState.UNKNOWN: lambda: tr("tui.runtime_management.process.unknown"),
}
_ROW_LABELS: dict[str, Callable[[], str]] = {
    "listener": lambda: tr("tui.runtime_management.labels.listener"),
    "manager-availability": lambda: tr("tui.runtime_management.labels.manager_availability"),
    "manager-kind": lambda: tr("tui.runtime_management.labels.manager_kind"),
    "provisioned": lambda: tr("tui.runtime_management.labels.provisioned"),
    "binding": lambda: tr("tui.runtime_management.labels.binding_matches"),
    "autostart": lambda: tr("tui.runtime_management.labels.login_autostart"),
    "process": lambda: tr("tui.runtime_management.labels.process_state"),
}


def _boolean_text(value: bool) -> str:
    return tr("flows.confirm.yes") if value else tr("flows.confirm.no")


def _read_off_loop(
    reader: RuntimeManagementReader, action: RuntimeManagementAction | None = None
) -> RuntimeManagementSnapshot:
    """Run even the inspector's synchronous setup outside Textual's UI loop."""

    async def invoke() -> RuntimeManagementSnapshot:
        if action is not None:
            await action()
        return await reader()

    return asyncio.run(invoke())


class RuntimeManagementCleanup:
    """Retain stop outcome and actual failed native owners across management screens."""

    def __init__(self) -> None:
        """Start one explicit management cleanup scope without native I/O."""
        self._consent: RuntimeStopConsent | None = None
        self._failure: BaseException | None = None
        self._resources: dict[int, AsyncCloseable] = {}
        self._retired: dict[int, AsyncCloseable] = {}

    @property
    def consent(self) -> RuntimeStopConsent | None:
        """Return the last exact consent, including its single-use dispatch fence."""
        return self._consent

    @property
    def failure(self) -> BaseException | None:
        """Return the original body failure or the current pending cleanup failure."""
        return self._failure

    @property
    def pending(self) -> bool:
        """Report actual release owners still retained by the enclosing scope."""
        return any(
            not isinstance(resource, RuntimeTransportCleanup) or not resource.released
            for resource in self._resources.values()
        )

    def retain_consent(self, consent: RuntimeStopConsent) -> None:
        """Keep the native outcome before its screen or worker can disappear."""
        self._consent = consent

    def retain(self, error: BaseException) -> None:
        """Adopt canonical owners directly, without adding an aggregate retry owner."""
        seen: set[int] = set()
        retained: AsyncResourceCleanupError | None = None
        for candidate in (error, error.__dict__.get("async_cleanup_error"), error.__dict__.get("cleanup_error")):
            if not isinstance(candidate, AsyncResourceCleanupError) or id(candidate) in seen:
                continue
            seen.add(id(candidate))
            retained = candidate if retained is None else retained.merged_with(candidate)
            for resource in candidate.resources:
                if self._retired.get(id(resource)) is resource:
                    continue
                if not isinstance(resource, RuntimeTransportCleanup) or not resource.released:
                    self._resources[id(resource)] = resource
        if retained is None:
            return
        if retained is not error:
            error.__dict__["async_cleanup_error"] = retained
            if isinstance(error.__dict__.get("cleanup_error"), AsyncResourceCleanupError):
                error.__dict__["cleanup_error"] = retained
        if self._failure is None or isinstance(error, asyncio.CancelledError):
            if self._failure is not None and self._failure is not error:
                error.__dict__["body_error"] = self._failure
            self._failure = error
        elif self._failure is not error:
            prior = self._failure.__dict__.get("async_cleanup_error")
            self._failure.__dict__["async_cleanup_error"] = (
                prior.merged_with(retained) if isinstance(prior, AsyncResourceCleanupError) else retained
            )

    @staticmethod
    def _replace_cleanup(error: BaseException, current: AsyncResourceCleanupError | None) -> None:
        """Keep active retry authority limited to this attempt's failed owners."""
        for name in ("async_cleanup_error", "cleanup_error"):
            previous = error.__dict__.get(name)
            if current is None:
                if isinstance(previous, AsyncResourceCleanupError):
                    error.__dict__.pop(name)
            elif (
                name == "async_cleanup_error"
                or isinstance(error, asyncio.CancelledError)
                or isinstance(previous, AsyncResourceCleanupError)
            ):
                error.__dict__[name] = current

    @staticmethod
    def _cleanup_errors(*errors: BaseException | None) -> tuple[AsyncResourceCleanupError, ...]:
        """Collect the active canonical owners before an attempt changes attachments."""
        return tuple(
            candidate
            for error in errors
            if error is not None
            for candidate in (error, error.__dict__.get("async_cleanup_error"), error.__dict__.get("cleanup_error"))
            if isinstance(candidate, AsyncResourceCleanupError)
        )

    async def release(self, *, primary_error: BaseException | None = None) -> None:
        """Release the actual retained resources under the enclosing scope's primary."""
        if primary_error is not None:
            self.retain(primary_error)
        prior_cleanup = self._cleanup_errors(primary_error, self._failure)
        resources = tuple(self._resources.values())
        failed: set[int] = set()
        try:
            # Keep this attempt's result separate from historical attachments.
            # The canonical helper still owns repeated caller cancellation and
            # attempts every actual resource; no aggregate owner is introduced.
            await close_async_resources(*resources, task_name="tui-runtime-management-release", primary_error=None)
        except BaseException as error:
            current = error if isinstance(error, AsyncResourceCleanupError) else error.__dict__.get("cleanup_error")
            if isinstance(current, AsyncResourceCleanupError):
                failed = {id(resource) for resource in current.resources}
            elif not isinstance(error, asyncio.CancelledError):
                # An unexpected helper failure cannot certify any release.
                failed = {id(resource) for resource in resources}
            if primary_error is not None:
                if isinstance(current, AsyncResourceCleanupError) or isinstance(error, asyncio.CancelledError):
                    self._replace_cleanup(
                        primary_error, current if isinstance(current, AsyncResourceCleanupError) else None
                    )
                    self.retain(primary_error)
                if isinstance(primary_error, asyncio.CancelledError):
                    raise primary_error from error
                if isinstance(error, asyncio.CancelledError):
                    error.__dict__["body_error"] = primary_error
                    self.retain(error)
                    raise
                if isinstance(error, AsyncResourceCleanupError):
                    return
            if primary_error is None and isinstance(error, AsyncResourceCleanupError):
                previous_failure = self._failure
                if previous_failure is not None and not isinstance(previous_failure, AsyncResourceCleanupError):
                    self._replace_cleanup(previous_failure, error)
                    self.retain(previous_failure)
                    raise previous_failure from error
                self._failure = error
                self.retain(error)
                if previous_failure is not None and previous_failure is not error:
                    raise error from previous_failure
            else:
                self.retain(error)
            raise
        else:
            if primary_error is not None:
                self._replace_cleanup(primary_error, None)
            if isinstance(self._failure, AsyncResourceCleanupError):
                self._failure = None
            elif self._failure is not None:
                self._replace_cleanup(self._failure, None)
            if isinstance(primary_error, asyncio.CancelledError):
                raise primary_error
        finally:
            released = tuple(resource for resource in resources if id(resource) not in failed)
            for retained in prior_cleanup + self._cleanup_errors(primary_error, self._failure):
                retained.discard_released_resources(*released)
            for resource in resources:
                if id(resource) not in failed:
                    self._resources.pop(id(resource), None)
                    self._retired[id(resource)] = resource
            for identity, resource in tuple(self._resources.items()):
                if isinstance(resource, RuntimeTransportCleanup) and resource.released:
                    self._resources.pop(identity)
                    self._retired[identity] = resource


class RuntimeStopConfirmationScreen(ModalScreen[bool]):
    """Require an explicit acknowledgement of the global runtime scope."""

    DEFAULT_CSS = """
    RuntimeStopConfirmationScreen { align: center middle; }
    #runtime-stop-confirm-body { width: 65; height: auto; border: round $warning; padding: 1 2; background: $surface; }
    """

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="runtime-stop-confirm-body"):
            yield Static(tr("tui.runtime_management.stop_scope"), markup=False)
            with Horizontal():
                yield Button(tr("tui.runtime_management.stop_confirm"), id="runtime-stop-confirm")
                yield Button(tr("tui.runtime_management.stop_cancel"), id="runtime-stop-cancel")

    @on(Button.Pressed, "#runtime-stop-confirm")
    def _confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#runtime-stop-cancel")
    def _cancel(self) -> None:
        self.dismiss(False)


class RuntimeManagementScreen(ModalScreen[None]):
    """Inspect and explicitly manage the local runtime without profile proof."""

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]
    DEFAULT_CSS = """
    RuntimeManagementScreen { align: center middle; }
    #runtime-management-body { width: 72; height: auto; border: round $accent; padding: 1 2; background: $surface; }
    #runtime-management-status { height: 2; }
    """

    def __init__(
        self,
        *,
        reader: RuntimeManagementReader = inspect_installed_runtime_management,
        starter: RuntimeManagementAction = start_installed_runtime_management,
        configurer: Callable[[bool], Awaitable[object]] | None = None,
        cleanup: RuntimeManagementCleanup | None = None,
    ) -> None:
        """Bind public status and explicit owner controls without profile proof."""
        super().__init__()
        self._reader = reader
        self._starter = starter
        self._configurer = configurer or self._configure_default
        self._live = True
        self._busy = False
        self._worker: Worker[None] | None = None
        self._cleanup = cleanup if cleanup is not None else RuntimeManagementCleanup()
        self._stop_consent: RuntimeStopConsent | None = self._cleanup.consent
        self._stop_error: BaseException | None = None
        self._stop_cleanup: AsyncResourceCleanupError | None = None

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="runtime-management-body"):
            yield Static(tr("tui.runtime_management.title"), markup=False)
            for selector, label in _ROW_LABELS.items():
                yield Static(
                    f"{label()}: {tr('tui.runtime_management.not_reported')}",
                    id=f"runtime-management-{selector}",
                    markup=False,
                )
            yield Static("", id="runtime-management-status", markup=False)
            with Horizontal():
                yield Button(tr("tui.runtime_access.refresh"), id="runtime-management-refresh")
                yield Button(tr("tui.runtime_management.start"), id="runtime-management-start")
                yield Button(tr("tui.runtime_management.enable"), id="runtime-management-enable")
                yield Button(tr("tui.runtime_management.disable"), id="runtime-management-disable")
                yield Button(tr("tui.runtime_management.stop"), id="runtime-management-stop")
                yield Button(tr("tui.runtime_access.close"), id="runtime-management-close")

    @staticmethod
    async def _configure_default(login_autostart: bool) -> object:
        return await configure_installed_runtime_management(login_autostart=login_autostart)

    def on_mount(self) -> None:
        """Start only after mounting so a completed read can update this screen."""
        self.call_after_refresh(self._start_refresh)

    async def on_unmount(self) -> None:
        """Own completion of any cancelled status read before the screen is discarded."""
        self._live = False
        worker = self._worker
        if worker is not None:
            worker.cancel()
            with suppress(WorkerCancelled, WorkerError, WorkerFailed, asyncio.CancelledError):
                await await_cancellation_complete(worker.wait(), task_name="tui-runtime-management-drain")
        # Installed Textual hosts swallow screen exceptions. Transfer the actual
        # owners to the enclosing explicit scope instead of raising a fatal UI
        # error or relying on destruction of this screen to release resources.
        consent = self._stop_consent
        if consent is not None and not consent.released:
            try:
                await consent.release(primary_error=self._stop_error)
            except BaseException as error:
                self._remember_stop_error(error)
            if self._stop_error is not None:
                self._cleanup.retain(self._stop_error)

    def _active(self) -> bool:
        return self._live and self.is_mounted

    def _start_refresh(self, action: RuntimeManagementAction | None = None) -> None:
        if not self._active() or self._busy:
            return
        self._busy = True
        try:
            self._worker = self.run_worker(self._refresh(action), group="runtime-management", exclusive=True)
        except Exception:
            self._busy = False
            raise

    def _row(self, selector: str, value: str) -> None:
        self.query_one(f"#runtime-management-{selector}", Static).update(f"{_ROW_LABELS[selector]()}: {value}")

    def _clear(self) -> None:
        unavailable = tr("tui.runtime_management.not_reported")
        for selector in _ROW_LABELS:
            self._row(selector, unavailable)

    def _render_snapshot(self, snapshot: RuntimeManagementSnapshot) -> None:
        self._row("listener", _LISTENER_TEXT[snapshot.listener]())
        self._row("manager-availability", _AVAILABILITY_TEXT[snapshot.manager_availability]())
        manager = snapshot.manager
        if manager is None:
            return
        self._row("manager-kind", _KIND_TEXT[manager.kind]())
        self._row("provisioned", _boolean_text(manager.provisioned))
        self._row("binding", _boolean_text(manager.binding_matches))
        self._row("autostart", _boolean_text(manager.login_autostart))
        self._row("process", _PROCESS_TEXT[manager.process_state]())

    async def _refresh(self, action: RuntimeManagementAction | None = None) -> None:
        if not self._active():
            self._busy = False
            return
        buttons = self._action_buttons()
        for button in buttons:
            button.disabled = True
        self._clear()
        self.query_one("#runtime-management-status", Static).update(tr("tui.runtime_management.busy"))
        try:
            observed = await await_cancellation_complete(
                asyncio.to_thread(_read_off_loop, self._reader, action), task_name="tui-runtime-management-status"
            )
            snapshot = RuntimeManagementSnapshot.model_validate(observed.model_dump(mode="python"), strict=True)
            if self._active():
                self._render_snapshot(snapshot)
                self.query_one("#runtime-management-status", Static).update(self._stop_status())
        except (Exception, asyncio.CancelledError):
            if self._active():
                self._clear()
                self.query_one("#runtime-management-status", Static).update(
                    self._stop_status() or tr("tui.runtime_management.refused")
                )
        finally:
            self._busy = False
            if self._active():
                for button in buttons:
                    button.disabled = button.id == "runtime-management-stop" and self._stop_fenced()

    def _stop_fenced(self) -> bool:
        consent = self._stop_consent
        return (
            self._cleanup.pending
            or self._stop_cleanup is not None
            or (consent is not None and (consent.accepted is not None or consent.uncertain or not consent.released))
        )

    def _remember_stop_error(self, error: BaseException) -> None:
        self._stop_error = error
        retained: AsyncResourceCleanupError | None = None
        seen: set[int] = set()
        for candidate in (error, error.__dict__.get("async_cleanup_error"), error.__dict__.get("cleanup_error")):
            if isinstance(candidate, AsyncResourceCleanupError) and id(candidate) not in seen:
                seen.add(id(candidate))
                retained = candidate if retained is None else retained.merged_with(candidate)
        self._stop_cleanup = retained
        self._cleanup.retain(error)

    def _stop_status(self) -> str:
        consent = self._stop_consent
        status = ""
        if consent is not None and consent.accepted is not None:
            status = tr("tui.runtime_management.stop_accepted")
        elif consent is not None and consent.uncertain:
            status = tr("tui.runtime_management.stop") + ": " + tr("tui.runtime_management.availability.unknown")
        elif self._stop_error is not None:
            status = tr("tui.runtime_management.refused")
        if self._stop_cleanup is not None:
            status += " · " + tr("tui.runtime_management.availability.unavailable")
        return status

    def _action_buttons(self) -> tuple[Button, ...]:
        return tuple(
            self.query_one(f"#runtime-management-{name}", Button)
            for name in ("refresh", "start", "enable", "disable", "stop")
        )

    async def _stop(self) -> None:
        if not self._active() or self._stop_fenced():
            return
        self._busy = True
        self._stop_error = None
        self._stop_cleanup = None
        buttons = self._action_buttons()
        for button in buttons:
            button.disabled = True
        consent: RuntimeStopConsent | None = None
        primary: BaseException | None = None
        try:
            consent = await preview_installed_runtime_stop()
            self._stop_consent = consent
            self._cleanup.retain_consent(consent)
            if not self._active():
                return
            acknowledged = await cast("App[object]", self.app).push_screen_wait(RuntimeStopConfirmationScreen())
            if not acknowledged or not self._active():
                return
            await consent.confirm()
        except BaseException as error:
            primary = error
        finally:
            if consent is not None:
                try:
                    await consent.release(primary_error=primary)
                except BaseException as error:
                    primary = error
            if primary is not None:
                self._remember_stop_error(primary)
            self._busy = False
            if self._active():
                self.query_one("#runtime-management-status", Static).update(self._stop_status())
                for button in buttons:
                    button.disabled = button.id == "runtime-management-stop" and self._stop_fenced()
        if primary is not None and not isinstance(primary, Exception):
            raise primary

    @on(Button.Pressed, "#runtime-management-refresh")
    def _refresh_pressed(self) -> None:
        self._start_refresh()

    @on(Button.Pressed, "#runtime-management-start")
    def _start_pressed(self) -> None:
        self._start_refresh(self._starter)

    @on(Button.Pressed, "#runtime-management-enable")
    def _enable_pressed(self) -> None:
        self._start_refresh(lambda: self._configurer(True))

    @on(Button.Pressed, "#runtime-management-disable")
    def _disable_pressed(self) -> None:
        self._start_refresh(lambda: self._configurer(False))

    @on(Button.Pressed, "#runtime-management-stop")
    def _stop_pressed(self) -> None:
        if not self._active() or self._busy or self._stop_fenced():
            return
        self._busy = True
        self._worker = self.run_worker(self._stop(), group="runtime-management", exclusive=True)

    @on(Button.Pressed, "#runtime-management-close")
    def _close_pressed(self) -> None:
        self.action_close()

    def action_close(self) -> None:
        """Dismiss with no authority result, including during a pending probe."""
        if self._active():
            self._live = False
            self.dismiss(None)


__all__ = ["RuntimeManagementAction", "RuntimeManagementCleanup", "RuntimeManagementReader", "RuntimeManagementScreen"]
