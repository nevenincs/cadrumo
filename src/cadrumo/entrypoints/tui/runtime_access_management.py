"""Standalone runtime-backed profile access controls for the TUI."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar, Literal, cast, override
from uuid import UUID

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static
from textual.worker import Worker, WorkerCancelled, WorkerError, WorkerFailed

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ...application.operations.registry import OperationFrontendProjection
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.user_profile.access_contracts import AccessDenialCode
from ...application.user_profile.access_projections import PublicAccessSession
from ...application.user_profile.automation_lifecycle import AutomationDenialKind, AutomationDenialReceipt
from ...application.user_profile.automation_lifecycle_service import AutomationResumeReceipt
from ...core.async_cleanup import await_cancellation_complete, close_async_resources
from ...core.i18n.render import tr
from .components.theme import tokenised
from .profile.automation_inventory import RuntimeAutomationInventoryScreen

if TYPE_CHECKING:
    from .secret.automation_requester import HumanAutomationRequesterFactory

type RecoveryClientOpener = Callable[[], Awaitable[RuntimeFrontendClient]]
type _Action = Literal[
    "refresh", "deny_key", "deny_grant", "deny_all", "lock_current", "lock_selected", "lock_profile", "resume"
]


def _grant_selection(raw: str) -> frozenset[UUID]:
    """Parse explicit selected grant identities; blank means human-only resume."""
    if not raw.strip():
        return frozenset[UUID]()
    parts = tuple(part.strip() for part in raw.split(","))
    if not all(parts):
        raise ValueError("empty selected grant")
    selected = tuple(UUID(part) for part in parts)
    if len(set(selected)) != len(selected):
        raise ValueError("repeated selected grant")
    return frozenset(selected)


def _session_rows(sessions: tuple[PublicAccessSession, ...]) -> str:
    """Show only allowlisted session facts, never a credential or custody key."""
    absent = tr("tui.automation_inventory.not_applicable")
    rows: list[str] = []
    for item in sorted(sessions, key=lambda item: item.session_id):
        scope = item.scope
        periods = (
            tr("tui.automation_inventory.all_periods")
            if scope.periods is None
            else ", ".join(str(period) for period in sorted(scope.periods, key=str))
            or tr("tui.automation_inventory.no_periods")
        )
        rows.append(
            tr(
                "tui.runtime_access.session_details",
                session_id=str(item.session_id),
                client_id=str(item.client_id),
                parent_session_id=str(item.parent_session_id) if item.parent_session_id is not None else absent,
                grant_id=str(item.grant_id) if item.grant_id is not None else absent,
                key_id=str(item.key_id) if item.key_id is not None else absent,
                kind=item.kind.value,
                state=item.state.value,
                expires_at=item.expires_at.isoformat(),
            )
        )
        for label, value in (
            ("operations", ", ".join(sorted(scope.operations))),
            ("actions", ", ".join(sorted(action.value for action in scope.actions))),
            (
                "disclosures",
                ", ".join(
                    f"{permission.destination_id}/{permission.projection_id}/{permission.category.value}"
                    for permission in sorted(
                        scope.disclosures,
                        key=lambda permission: (
                            str(permission.destination_id),
                            str(permission.projection_id),
                            permission.category.value,
                        ),
                    )
                ),
            ),
            ("periods", periods),
            ("delegation", tr("flows.confirm.yes") if scope.allow_delegation else tr("flows.confirm.no")),
            (
                "period_independent",
                tr("flows.confirm.yes") if scope.allow_period_independent else tr("flows.confirm.no"),
            ),
        ):
            rows.append(f"{tr(f'tui.automation_inventory.{label}')}: {value or absent}")
    return "\n".join(rows)


def _denial_acknowledgement(receipt: AutomationDenialReceipt) -> str:
    return tr(
        "tui.runtime_access.denial_acknowledgement",
        access_denied=tr("flows.confirm.yes") if receipt.access_denied else tr("flows.confirm.no"),
        cleanup_pending=tr("flows.confirm.yes") if receipt.cleanup_pending else tr("flows.confirm.no"),
    )


class _RecoveryClientCleanup:
    """Retain one blocking connection until its native close succeeds."""

    def __init__(self, client: RuntimeFrontendClient, *, released: Callable[[], None]) -> None:
        self._client = client
        self._released = released

    async def close(self) -> None:
        await asyncio.to_thread(self._client.close)
        self._released()


class RuntimeAccessManagementScreen(ModalScreen[None]):
    """Borrow one admitted TUI client and separately own each recovery connection.

    The installed account lifecycle supplies the exact admitted connection.
    This screen does not select a profile or open local custody.
    """

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]
    DEFAULT_CSS = tokenised("""
    RuntimeAccessManagementScreen { align: center middle; }
    #runtime-access-body {
        width: $cadrumo-modal-width;
        height: $cadrumo-modal-height;
        border: $cadrumo-radius-overlay $accent;
        padding: $cadrumo-gutter-y $cadrumo-gutter;
        background: $surface;
    }
    #runtime-access-content { height: 1fr; }
    #runtime-access-sessions { height: auto; }
    #runtime-access-status { height: auto; }
    #runtime-access-actions { height: auto; }
    """)

    def __init__(
        self,
        client: RuntimeFrontendClient,
        *,
        open_recovery_client: RecoveryClientOpener,
        requester_factory: HumanAutomationRequesterFactory | None = None,
    ) -> None:
        """Pin exact profile/TUI ownership without retaining any password."""
        super().__init__()
        if client.frontend is not OperationFrontendProjection.TUI:
            raise ValueError("access management requires a TUI frontend client")
        self._profile_id = client.profile_id
        self._session_id = client.session_id
        self._client = client
        self._open_recovery_client = open_recovery_client
        self._requester_factory = requester_factory
        self._busy = False
        self._access_lost = False
        self._admin_available = False
        self._screen_live = True
        self._worker: Worker[None] | None = None
        self._password_input: Input | None = None
        self._recovery_clients: dict[int, _RecoveryClientCleanup] = {}
        self._resume_dispatched = False
        self._resume_uncertain_code: str | None = None
        self._resume_receipt: AutomationResumeReceipt | None = None

    @property
    def access_lost(self) -> bool:
        """Whether this screen has retired its admission while it was open."""
        return self._access_lost

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="runtime-access-body"):
            yield Static(tr("tui.runtime_access.title"))
            with VerticalScroll(id="runtime-access-content"):
                yield Static(tr("tui.runtime_access.sessions"))
                yield Static(tr("tui.runtime_access.sessions_empty"), id="runtime-access-sessions", markup=False)
                with Horizontal(id="runtime-access-actions"):
                    yield Button(tr("tui.runtime_access.refresh"), id="runtime-access-refresh")
                    yield Button(tr("tui.runtime_access.view_automation"), id="runtime-access-view-automation")
                    if self._requester_factory is not None:
                        yield Button(tr("tui.automation_request.enroll"), id="runtime-access-create-automation")
                    yield Button(tr("tui.runtime_access.lock_current"), id="runtime-access-lock-current")
                    yield Button(tr("tui.runtime_access.lock_profile"), id="runtime-access-lock-profile")
                yield Static(tr("tui.runtime_access.deny_target"))
                yield Input(id="runtime-access-target")
                with Horizontal():
                    yield Button(tr("tui.runtime_access.revoke_session"), id="runtime-access-lock-selected")
                    yield Button(tr("tui.runtime_access.deny_key"), id="runtime-access-deny-key")
                    yield Button(tr("tui.runtime_access.deny_grant"), id="runtime-access-deny-grant")
                    yield Button(tr("tui.runtime_access.deny_all"), id="runtime-access-deny-all")
                yield Static(tr("tui.runtime_access.resume_password"))
                yield Input(password=True, id="runtime-access-password")
                yield Static(tr("tui.runtime_access.resume_grants"))
                yield Input(id="runtime-access-grants")
                yield Button(tr("tui.runtime_access.resume"), id="runtime-access-resume")
            yield Static("", id="runtime-access-status", markup=False)
            yield Button(tr("tui.runtime_access.close"), id="runtime-access-close")

    def on_mount(self) -> None:
        """Read only the current bound session's public inventory."""
        self._password_input = self.query_one("#runtime-access-password", Input)
        self._controls()
        self.call_after_refresh(self._initial_refresh)

    def _initial_refresh(self) -> None:
        """Start only once the installed screen can retain the returned view."""
        if not self._active() or self._busy:
            return
        self._worker = self.run_worker(self._perform("refresh"), group="runtime-access", exclusive=True)

    async def on_unmount(self) -> None:
        """Drain this screen's worker and proof without closing its borrowed client."""
        self._screen_live = False
        if self._password_input is not None:
            self._password_input.value = ""
            self._password_input = None
        try:
            worker = self._worker
            if worker is not None:
                worker.cancel()
                with suppress(WorkerCancelled, WorkerError, WorkerFailed):
                    await await_cancellation_complete(worker.wait(), task_name="tui-runtime-access-drain")
        finally:
            await close_async_resources(
                *tuple(self._recovery_clients.values()), task_name="tui-recovery-connections-release"
            )

    def _active(self) -> bool:
        return self._screen_live and self.is_mounted

    def _controls(self) -> None:
        if not self._active():
            return
        admitted = not self._busy and not self._access_lost
        admin = admitted and self._admin_available
        for suffix in (
            "refresh",
            "view-automation",
            "lock-selected",
            "lock-profile",
            "deny-key",
            "deny-grant",
            "deny-all",
        ):
            self.query_one(f"#runtime-access-{suffix}", Button).disabled = not admin
        self.query_one("#runtime-access-lock-current", Button).disabled = not admitted
        if self._requester_factory is not None:
            self.query_one("#runtime-access-create-automation", Button).disabled = not admin
        self.query_one("#runtime-access-resume", Button).disabled = (
            self._busy or self._resume_uncertain_code is not None or self._resume_receipt is not None
        )
        self.query_one("#runtime-access-close", Button).disabled = self._busy

    def _status(self, key: str, *, code: str | None = None) -> None:
        if not self._active():
            return
        message = tr(key)
        self.query_one("#runtime-access-status", Static).update(message if code is None else f"{message} ({code})")

    def _resume_unknown(self, code: str) -> None:
        """Retain uncertainty after dispatch instead of offering another mutation."""
        self._resume_uncertain_code = code
        if self._active():
            self.query_one("#runtime-access-status", Static).update(
                f"{tr('tui.runtime_access.resume')}: {tr('tui.runtime_management.availability.unknown')} ({code})"
            )

    def _resume_fenced(self) -> bool:
        """Guard rendered and programmatic retries, without claiming a new admission."""
        if self._resume_receipt is None and self._resume_uncertain_code is None:
            return False
        if self._active():
            self.query_one("#runtime-access-password", Input).value = ""
            self.query_one("#runtime-access-grants", Input).value = ""
        if self._resume_receipt is not None:
            self._status(
                "tui.runtime_access.completed",
                code=RuntimeRefusalCode.UNAVAILABLE.value if self._recovery_clients else None,
            )
        else:
            self._resume_unknown(self._resume_uncertain_code or RuntimeRefusalCode.UNAVAILABLE.value)
        return True

    def _resume_failed(self, *, code: str, uncertain: bool) -> None:
        """Separate a validated effect from failed cleanup or an unknown dispatch."""
        if self._resume_receipt is not None:
            self._status("tui.runtime_access.completed", code=code)
        elif self._resume_dispatched and uncertain:
            self._resume_unknown(code)
        else:
            self._resume_dispatched = False
            self._status("tui.runtime_access.refused", code=code)

    def _lose_access(self) -> None:
        self._access_lost = True
        self._admin_available = False
        if self._active():
            self.query_one("#runtime-access-sessions", Static).update("")
        self._controls()

    def _show_sessions(self, sessions: tuple[PublicAccessSession, ...]) -> None:
        if not self._active() or self._access_lost:
            return
        if not self._binding_is_current() or any(item.profile_id != self._profile_id for item in sessions):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._admin_available = True
        rows = _session_rows(sessions)
        self.query_one("#runtime-access-sessions", Static).update(rows or tr("tui.runtime_access.sessions_empty"))

    async def _retain_self_lock_after_human_refusal(self) -> bool:
        """Confirm this exact lease remains live without claiming admin rights."""
        try:
            reply = await await_cancellation_complete(
                asyncio.to_thread(self._client.status), task_name="tui-access-current-session-status"
            )
        except Exception:
            return False
        status = reply.status
        if (
            not status.connected
            or not status.credential_authenticated
            or not status.profile_bound
            or status.profile_id != self._profile_id
            or status.session_id != self._session_id
            or status.session_expires_at is None
            or status.session_expires_at <= datetime.now(UTC)
            or status.denial is not None
        ):
            return False
        self._admin_available = False
        if self._active():
            self.query_one("#runtime-access-sessions", Static).update("")
        return True

    async def _recover_owned(self, password: bytearray, grants: frozenset[UUID]) -> None:
        """Own opener, protected call and close as one cancellation-complete task."""
        try:
            recovery_client = await self._open_recovery_client()
            identity = id(recovery_client)
            cleanup = self._recovery_clients.get(identity)
            if cleanup is None:

                def released() -> None:
                    self._recovery_clients.pop(identity, None)

                cleanup = _RecoveryClientCleanup(recovery_client, released=released)
                self._recovery_clients[identity] = cleanup
            try:
                if not self._active():
                    return
                if (
                    recovery_client.profile_id != self._profile_id
                    or recovery_client.frontend is not OperationFrontendProjection.TUI
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                self._resume_dispatched = True
                try:
                    observed = await await_cancellation_complete(
                        asyncio.to_thread(recovery_client.recover_profile, password, grants=grants),
                        task_name="tui-recovery-native-proof",
                    )
                finally:
                    # No cleanup wait may retain a proof after its native reader has settled.
                    password[:] = bytes(len(password))
                receipt = AutomationResumeReceipt.model_validate(observed.model_dump(mode="python"), strict=True)
                if receipt.profile_id != self._profile_id or receipt.reactivated_grants != grants:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                self._resume_receipt = receipt
            finally:
                password[:] = bytes(len(password))
                await close_async_resources(cleanup, task_name="tui-recovery-connection-close")
        finally:
            password[:] = bytes(len(password))

    async def _perform(self, action: _Action) -> None:
        if self._busy or not self._active():
            return
        if action == "resume":
            if self._resume_fenced():
                return
            self._resume_dispatched = False
        self._busy = True
        self._controls()
        self._status("tui.runtime_access.busy")
        acknowledgement: str | None = None
        try:
            if action == "refresh":
                sessions = await await_cancellation_complete(
                    asyncio.to_thread(self._client.sessions), task_name="tui-access-session-inventory"
                )
                self._show_sessions(sessions)
            elif action in {"deny_key", "deny_grant", "deny_all"}:
                target: UUID | None = None
                if action != "deny_all":
                    try:
                        target = UUID(self.query_one("#runtime-access-target", Input).value.strip())
                    except ValueError:
                        self._status("tui.runtime_access.invalid_target")
                        return
                kind = {
                    "deny_key": AutomationDenialKind.KEY,
                    "deny_grant": AutomationDenialKind.GRANT,
                    "deny_all": AutomationDenialKind.ALL,
                }[action]
                denied = await await_cancellation_complete(
                    asyncio.to_thread(self._client.deny_automation, kind, target_id=target),
                    task_name="tui-access-denial",
                )
                if denied.profile_id != self._profile_id:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                acknowledgement = _denial_acknowledgement(denied)
                if self._active():
                    self.query_one("#runtime-access-target", Input).value = ""
            elif action == "lock_current":
                locked = await await_cancellation_complete(
                    asyncio.to_thread(self._client.lock), task_name="tui-current-session-lock"
                )
                if self._session_id not in locked.session_ids:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                acknowledgement = tr(
                    "tui.runtime_access.sessions_locked", session_ids=", ".join(map(str, locked.session_ids))
                )
                self._lose_access()
            elif action == "lock_selected":
                try:
                    target_session_id = UUID(self.query_one("#runtime-access-target", Input).value.strip())
                except ValueError:
                    self._status("tui.runtime_access.invalid_target")
                    return
                locked = await await_cancellation_complete(
                    asyncio.to_thread(self._client.revoke_session, target_session_id),
                    task_name="tui-selected-session-lock",
                )
                acknowledgement = tr(
                    "tui.runtime_access.sessions_locked", session_ids=", ".join(map(str, locked.session_ids))
                )
                if self._active():
                    self.query_one("#runtime-access-target", Input).value = ""
                if self._session_id in locked.session_ids:
                    self._lose_access()
                else:
                    sessions = await await_cancellation_complete(
                        asyncio.to_thread(self._client.sessions), task_name="tui-access-session-inventory"
                    )
                    self._show_sessions(sessions)
            elif action == "lock_profile":
                denied = await await_cancellation_complete(
                    asyncio.to_thread(self._client.deny_automation, AutomationDenialKind.PROFILE_LOCK),
                    task_name="tui-profile-lock",
                )
                if denied.profile_id != self._profile_id:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                acknowledgement = _denial_acknowledgement(denied)
                self._lose_access()
            else:
                password_input = self.query_one("#runtime-access-password", Input)
                password = bytearray(password_input.value.encode("utf-8"))
                password_input.value = ""
                try:
                    grants = _grant_selection(self.query_one("#runtime-access-grants", Input).value)
                except ValueError:
                    password[:] = bytes(len(password))
                    self._status("tui.runtime_access.invalid_grants")
                    return
                await await_cancellation_complete(
                    self._recover_owned(password, grants), task_name="tui-profile-recovery"
                )
                if self._active():
                    self.query_one("#runtime-access-grants", Input).value = ""
            self._status("tui.runtime_access.completed")
            if acknowledgement is not None and self._active():
                self.query_one("#runtime-access-status", Static).update(acknowledgement)
        except (RuntimeFrontendRefusedError, RuntimeRefusalError) as error:
            code = error.reason if isinstance(error, RuntimeFrontendRefusedError) else error.reason.value
            if (
                action not in {"lock_current", "resume"}
                and isinstance(error, RuntimeFrontendRefusedError)
                and error.reason == AccessDenialCode.HUMAN_AUTHORITY_REQUIRED.value
                and await self._retain_self_lock_after_human_refusal()
            ):
                self._status("tui.runtime_access.refused", code=code)
            elif action != "resume":
                self._lose_access()
                self._status("tui.runtime_access.access_lost", code=code)
            else:
                self._resume_failed(
                    code=code,
                    uncertain=isinstance(error, RuntimeRefusalError)
                    or error.reason in {item.value for item in RuntimeRefusalCode},
                )
        except asyncio.CancelledError:
            if action == "resume":
                self._resume_failed(code=RuntimeRefusalCode.UNAVAILABLE.value, uncertain=True)
            raise
        except Exception:
            if action == "resume":
                self._resume_failed(code=RuntimeRefusalCode.UNAVAILABLE.value, uncertain=True)
            else:
                self._lose_access()
                self._status("tui.runtime_access.access_lost")
        finally:
            self._busy = False
            if self._active():
                if action == "resume":
                    self.query_one("#runtime-access-password", Input).value = ""
                    self.query_one("#runtime-access-grants", Input).value = ""
                self._controls()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Map only the rendered controls to their bound runtime actions."""
        if event.button.id == "runtime-access-close":
            self.action_close()
            return
        if self._busy:
            return
        if event.button.id == "runtime-access-create-automation":
            factory = self._requester_factory
            if self._admin_available and not self._access_lost and factory is not None:
                if not self._binding_is_current():
                    self._lose_access()
                    return
                try:
                    requester = factory(self._client)
                    cast("App[object]", self.app).push_screen(requester, lambda _: self._on_requester_closed())
                except Exception:
                    self._status("tui.runtime_access.refused")
            return
        if event.button.id == "runtime-access-view-automation":
            if self._admin_available and not self._access_lost:
                inventory = RuntimeAutomationInventoryScreen(self._client)
                cast("App[object]", self.app).push_screen(
                    inventory, lambda lost: self._on_inventory_closed(inventory, lost)
                )
            return
        actions: dict[str, _Action] = {
            "runtime-access-refresh": "refresh",
            "runtime-access-deny-key": "deny_key",
            "runtime-access-deny-grant": "deny_grant",
            "runtime-access-deny-all": "deny_all",
            "runtime-access-lock-current": "lock_current",
            "runtime-access-lock-selected": "lock_selected",
            "runtime-access-lock-profile": "lock_profile",
            "runtime-access-resume": "resume",
        }
        action = actions.get(event.button.id or "")
        if action is not None:
            if action == "resume" and self._resume_fenced():
                return
            self._worker = self.run_worker(self._perform(action), group="runtime-access", exclusive=True)

    def _on_inventory_closed(self, screen: RuntimeAutomationInventoryScreen, lost: bool | None) -> None:
        """A closed child cannot restore a lost parent admission."""
        if lost or screen.access_lost:
            self._lose_access()

    def _binding_is_current(self) -> bool:
        try:
            return (
                self._client.profile_id == self._profile_id
                and self._client.session_id == self._session_id
                and self._client.frontend is OperationFrontendProjection.TUI
            )
        except Exception:
            return False

    def _on_requester_closed(self) -> None:
        """Refresh facts after settlement without replaying the submitted request."""
        if not self._active():
            return
        if not self._binding_is_current():
            self._lose_access()
            return
        self._initial_refresh()

    def action_close(self) -> None:
        """Close only after any native exchange and owned cleanup settle."""
        if not self._busy:
            self.dismiss(None)


__all__ = ["RecoveryClientOpener", "RuntimeAccessManagementScreen"]
