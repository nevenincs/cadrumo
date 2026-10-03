"""A bounded status shell for an admitted API-key TUI session."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import ClassVar, Literal, override
from uuid import UUID

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Static

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ...application.operations.registry import OperationFrontendProjection
from ...application.runtime.contracts import RuntimeRefusalError
from ...application.runtime.profile_access import status_admits_session
from ...application.user_profile.access_contracts import ProfileAccessStatus
from ...core.async_cleanup import await_cancellation_complete
from ...core.i18n.render import tr
from ...core.time.clock import now
from .account import AccountRecomposeReasonV1, AccountRecomposeRequiredV1
from .components.theme import BASE_CSS, install_cadrumo_themes, tokenised
from .runtime_management import RuntimeManagementScreen
from .runtime_management_cleanup import RuntimeManagementCleanup
from .secret.automation_requester import RuntimeAutomationRequesterScreen

_STATUS_INTERVAL_SECONDS = 10.0
type _LockAction = Literal["sign_out", "change_user"]
type RestrictedRequesterFactory = Callable[[RuntimeFrontendClient], RuntimeAutomationRequesterScreen]


def _restricted_disclosures(status: ProfileAccessStatus, empty: str) -> str:
    scope = status.effective_scope
    disclosures = sorted(
        scope.disclosures,
        key=lambda permission: (
            str(permission.destination_id),
            str(permission.projection_id),
            permission.category.value,
        ),
    )
    values = (
        f"{permission.destination_id}/{permission.projection_id}/{permission.category.value}"
        for permission in disclosures
    )
    return ", ".join(values) or empty


def _restricted_periods(status: ProfileAccessStatus, empty: str) -> str:
    periods = status.effective_scope.periods
    if periods is None:
        return tr("tui.restricted.all_periods")
    values = ", ".join(str(item) for item in sorted(periods, key=lambda item: (item.filing_year, str(item.code))))
    return values or empty


def _restricted_period_independent(status: ProfileAccessStatus) -> str:
    key = "tui.restricted.yes" if status.effective_scope.allow_period_independent else "tui.restricted.no"
    return tr(key)


def _restricted_scope_text(status: ProfileAccessStatus) -> tuple[str, str, str, str, str]:
    scope = status.effective_scope
    empty = tr("tui.restricted.none")
    operations = ", ".join(sorted(str(item) for item in scope.operations)) or empty
    actions = ", ".join(sorted(item.value for item in scope.actions)) or empty
    disclosures = _restricted_disclosures(status, empty)
    delegation = tr("tui.restricted.yes") if scope.allow_delegation else tr("tui.restricted.no")
    periods = _restricted_periods(status, empty)
    return operations, actions, disclosures, delegation, periods


class RuntimeRestrictedSessionApp(App[AccountRecomposeRequiredV1 | None]):
    """Show one API lease without borrowing human workbench or admin authority."""

    BINDINGS: ClassVar = [Binding("q", "leave", "", show=False)]
    CSS = tokenised(BASE_CSS)

    def __init__(
        self,
        client: RuntimeFrontendClient,
        *,
        profile_label: str,
        requester_factory: RestrictedRequesterFactory | None = None,
        runtime_management_cleanup: RuntimeManagementCleanup | None = None,
    ) -> None:
        """Pin the caller-owned TUI connection without taking ownership of close."""
        super().__init__()
        if client.frontend is not OperationFrontendProjection.TUI or not profile_label:
            raise ValueError("restricted session requires an exact TUI client and profile label")
        self._client = client
        self._profile_id: UUID = client.profile_id
        self._session_id: UUID = client.session_id
        self._profile_label = profile_label
        self._requester_factory = requester_factory
        self._runtime_management_cleanup = (
            RuntimeManagementCleanup() if runtime_management_cleanup is None else runtime_management_cleanup
        )
        self._cleared = False
        self._locking = False
        self._reading = False

    @override
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(tr("tui.restricted.title"), id="restricted-title")
            yield Static("", id="restricted-profile", markup=False)
            yield Static("", id="restricted-session-expiry", markup=False)
            yield Static("", id="restricted-grant", markup=False)
            yield Static("", id="restricted-operations", markup=False)
            yield Static("", id="restricted-actions", markup=False)
            yield Static("", id="restricted-disclosures", markup=False)
            yield Static("", id="restricted-delegation", markup=False)
            yield Static("", id="restricted-periods", markup=False)
            yield Static("", id="restricted-availability", markup=False)
            with Horizontal():
                if self._requester_factory is not None:
                    yield Button(tr("tui.automation_request.title"), id="restricted-request-access")
                yield Button(tr("tui.runtime_management.open"), id="restricted-runtime-status")
                yield Button(tr("tui.restricted.lock"), id="restricted-lock")
                yield Button(tr("tui.restricted.change_user"), id="restricted-change-user")
                yield Button(tr("tui.restricted.close"), id="restricted-close")
        yield Footer()

    def on_mount(self) -> None:
        """Start non-touching status observation after the shell has mounted."""
        install_cadrumo_themes(self)
        self.set_interval(_STATUS_INTERVAL_SECONDS, self._start_status_read)
        self._start_status_read()

    def on_unmount(self) -> None:
        """Fence late status results when the borrowed shell is discarded."""
        self._cleared = True

    def _binding_is_current(self) -> bool:
        try:
            return (
                self._client.frontend is OperationFrontendProjection.TUI
                and self._client.profile_id == self._profile_id
                and self._client.session_id == self._session_id
            )
        except (RuntimeFrontendRefusedError, RuntimeRefusalError):
            return False

    def _status_is_current(self, status: ProfileAccessStatus) -> bool:
        return self._binding_is_current() and status_admits_session(
            status,
            profile_id=self._profile_id,
            session_id=self._session_id,
            at=now(),
            requires_automation_grant=True,
        )

    def _start_status_read(self) -> None:
        if not self._cleared and not self._locking and not self._reading:
            self._reading = True
            self.run_worker(self._read_status(), group="restricted-status")

    async def _read_status(self) -> None:
        try:
            if not self._binding_is_current():
                self._expire()
                return
            reply = await await_cancellation_complete(
                asyncio.to_thread(self._client.status), task_name="tui-restricted-status"
            )
            if self._cleared or self._locking:
                return
            if not self._status_is_current(reply.status):
                self._expire()
                return
            self._render_status(reply.status)
        except (Exception, asyncio.CancelledError):
            if not self._cleared and not self._locking:
                self._expire()
        finally:
            self._reading = False

    def _render_status(self, status: ProfileAccessStatus) -> None:
        """Render only the canonical non-secret effective scope and health axes."""
        operations, actions, disclosures, delegation, periods = _restricted_scope_text(status)
        if status.session_expires_at is None or status.grant_expires_at is None:
            self._expire()
            return
        self.query_one("#restricted-profile", Static).update(
            tr("tui.restricted.profile", label=self._profile_label, profile_id=str(self._profile_id))
        )
        self.query_one("#restricted-session-expiry", Static).update(
            tr("tui.restricted.session_expiry", expires_at=status.session_expires_at.isoformat())
        )
        self.query_one("#restricted-grant", Static).update(
            tr("tui.restricted.grant", valid=tr("tui.restricted.yes"), expires_at=status.grant_expires_at.isoformat())
        )
        self.query_one("#restricted-operations", Static).update(tr("tui.restricted.operations", values=operations))
        self.query_one("#restricted-actions", Static).update(tr("tui.restricted.actions", values=actions))
        self.query_one("#restricted-disclosures", Static).update(
            f"{tr('tui.automation_inventory.disclosures')}: {disclosures}"
        )
        self.query_one("#restricted-delegation", Static).update(
            f"{tr('tui.automation_inventory.delegation')}: {delegation}"
        )
        self.query_one("#restricted-periods", Static).update(
            tr(
                "tui.restricted.periods",
                values=periods,
                independent=_restricted_period_independent(status),
            )
        )
        self.query_one("#restricted-availability", Static).update(
            tr(
                "tui.restricted.availability",
                storage=status.storage.value,
                authority=status.published_authority.value,
                provider=status.provider.value,
            )
        )

    def _clear_presentation(self) -> None:
        self._cleared = True
        for selector in (
            "#restricted-profile",
            "#restricted-session-expiry",
            "#restricted-grant",
            "#restricted-operations",
            "#restricted-actions",
            "#restricted-disclosures",
            "#restricted-delegation",
            "#restricted-periods",
            "#restricted-availability",
        ):
            self.query_one(selector, Static).update("")
        self.query_one("#restricted-lock", Button).disabled = True
        self.query_one("#restricted-change-user", Button).disabled = True
        if self._requester_factory is not None:
            self.query_one("#restricted-request-access", Button).disabled = True

    def _expire(self) -> None:
        if self._cleared:
            return
        self._clear_presentation()
        self.exit(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED))

    def _begin_lock(self, action: _LockAction) -> None:
        if self._cleared or self._locking:
            return
        self._locking = True
        self._clear_presentation()
        self.run_worker(self._finish_lock(action), name="restricted-session-lock")

    async def _finish_lock(self, action: _LockAction) -> None:
        reason = AccountRecomposeReasonV1.EXPIRED
        try:
            if self._binding_is_current():
                locked = await await_cancellation_complete(
                    asyncio.to_thread(self._client.lock), task_name="tui-restricted-lock"
                )
                if self._session_id in locked.session_ids:
                    reason = (
                        AccountRecomposeReasonV1.CHANGE_USER
                        if action == "change_user"
                        else AccountRecomposeReasonV1.SIGNED_OUT
                    )
        except (Exception, asyncio.CancelledError):
            reason = AccountRecomposeReasonV1.EXPIRED
        if self.is_running:
            self.exit(AccountRecomposeRequiredV1(reason=reason))

    @on(Button.Pressed, "#restricted-lock")
    def _lock_pressed(self) -> None:
        self._begin_lock("sign_out")

    @on(Button.Pressed, "#restricted-change-user")
    def _change_user_pressed(self) -> None:
        self._begin_lock("change_user")

    @on(Button.Pressed, "#restricted-close")
    def _close_pressed(self) -> None:
        self.action_leave()

    @on(Button.Pressed, "#restricted-request-access")
    def _request_access_pressed(self) -> None:
        """Open an own-grant request using only the already bound API client."""
        factory = self._requester_factory
        if not self._cleared and not self._locking and self._binding_is_current() and factory is not None:
            try:
                self.push_screen(factory(self._client))
            except Exception:
                self.query_one("#restricted-availability", Static).update(tr("tui.automation_request.invalid"))

    @on(Button.Pressed, "#restricted-runtime-status")
    def _runtime_status_pressed(self) -> None:
        """Inspect the passive runtime manager independently of API authority."""
        if not self._locking:
            self.push_screen(RuntimeManagementScreen(cleanup=self._runtime_management_cleanup))

    def action_leave(self) -> None:
        """Leave normally without revoking another authority or closing the client."""
        if not self._locking:
            self._clear_presentation()
            self.exit(None)


__all__ = ["RuntimeRestrictedSessionApp"]
