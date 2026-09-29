"""Human automation inventory presented from one bound runtime session."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime
from typing import ClassVar, cast, override
from uuid import UUID

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Button, DataTable, Static
from textual.worker import Worker, WorkerCancelled, WorkerError, WorkerFailed

from ....adapters.local_runtime.automation_inventory import read_automation_inventory
from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.operations.registry import OperationFrontendProjection
from ....application.user_profile.automation_enrollment import (
    AutomationGrantProjection,
    AutomationInventoryProjection,
    AutomationKeyProjection,
    AutomationReviewProjection,
    AutomationScopeProjection,
)
from ....core.async_cleanup import await_cancellation_complete
from ....core.i18n.render import tr
from ..secret.automation_decision import AutomationDecisionUiOutcome, RuntimeAutomationDecisionScreen


def _value(value: object) -> str:
    if isinstance(value, bool):
        return tr("flows.confirm.yes") if value else tr("flows.confirm.no")
    return str(value)


def _detail(label: str, value: object) -> str:
    return f"{tr(f'tui.automation_inventory.{label}')}: {_value(value)}"


def _scope(scope: AutomationScopeProjection) -> tuple[str, ...]:
    disclosures = tuple(
        f"{item.destination_id}/{item.projection_id}/{item.category.value}" for item in scope.disclosures
    )
    if scope.periods is None:
        periods = tr("tui.automation_inventory.all_periods")
    elif not scope.periods:
        periods = tr("tui.automation_inventory.no_periods")
    else:
        periods = ", ".join(f"{item.filing_year}/{item.code}" for item in scope.periods)
    return (
        _detail("operations", ", ".join(scope.operations)),
        _detail("actions", ", ".join(item.value for item in scope.actions)),
        _detail("disclosures", ", ".join(disclosures)),
        _detail("periods", periods),
        _detail("delegation", scope.allow_delegation),
        _detail("period_independent", scope.allow_period_independent),
    )


def _grant_detail(item: AutomationGrantProjection) -> str:
    return "\n".join(
        (
            _detail("id", item.grant_id),
            _detail("client", item.client_id),
            _detail("state", item.state.value),
            _detail("expires", item.expires_at.isoformat()),
            *_scope(item.scope),
            _detail("unattended", item.unattended),
            _detail("os_lock", item.allow_os_lock),
        )
    )


def _key_detail(item: AutomationKeyProjection) -> str:
    return "\n".join(
        (
            _detail("id", item.key_id),
            _detail("grant", item.grant_id),
            _detail("state", item.state.value),
            _detail("expires", item.expires_at.isoformat()),
            _detail("last_used", item.last_used_at.isoformat() if item.last_used_at is not None else ""),
        )
    )


def _request_detail(item: AutomationReviewProjection) -> str:
    return "\n".join(
        (
            _detail("profile", item.receipt.profile_id),
            _detail("id", item.receipt.request_id),
            _detail("review_digest", item.receipt.review_digest),
            _detail("client", item.client_id),
            _detail("destination", item.destination_id),
            _detail("state", item.receipt.stage.value),
            _detail("expires", item.expires_at.isoformat()),
            _detail("kind", item.proposal.kind.value),
            _detail("grant_expires", item.proposal.expires_at.isoformat()),
            _detail(
                "key_expires",
                item.proposal.key_expires_at.isoformat() if item.proposal.key_expires_at is not None else "",
            ),
            _detail("target_grant", item.proposal.target_grant_id or ""),
            _detail("target_key", item.proposal.target_key_id or ""),
            *_scope(item.proposal.scope),
            _detail("unattended", item.proposal.unattended),
            _detail("os_lock", item.proposal.allow_os_lock),
        )
    )


class RuntimeAutomationInventoryScreen(ModalScreen[bool | None]):
    """Borrow one TUI session; the runtime remains the sole inventory authority."""

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]
    DEFAULT_CSS = """
    RuntimeAutomationInventoryScreen { align: center middle; }
    #automation-inventory-body { width: 112; height: 38; border: round $accent; padding: 1 2; background: $surface; }
    #automation-inventory-content { height: 1fr; }
    #automation-inventory-grants, #automation-inventory-keys, #automation-inventory-requests { height: 5; }
    #automation-inventory-details { height: 1fr; }
    """

    def __init__(self, client: RuntimeFrontendClient) -> None:
        """Pin one admitted TUI connection without assuming inventory privilege."""
        super().__init__()
        if client.frontend is not OperationFrontendProjection.TUI:
            raise ValueError("automation inventory requires a TUI frontend")
        self._client = client
        self._profile_id: UUID = client.profile_id
        self._session_id: UUID = client.session_id
        self._inventory: AutomationInventoryProjection | None = None
        self._selected_review: AutomationReviewProjection | None = None
        self._worker: Worker[None] | None = None
        self._busy = False
        self._live = True
        self._access_lost = False
        self._known_session_expires_at: datetime | None = None
        self._lifetime_timer: Timer | None = None

    @property
    def access_lost(self) -> bool:
        """Report whether the original profile session failed its binding check."""
        return self._access_lost

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="automation-inventory-body"):
            yield Static(tr("tui.automation_inventory.title"))
            with VerticalScroll(id="automation-inventory-content"):
                yield Static(tr("tui.automation_inventory.grants"))
                yield DataTable(id="automation-inventory-grants", cursor_type="row", zebra_stripes=True)
                yield Static(tr("tui.automation_inventory.keys"))
                yield DataTable(id="automation-inventory-keys", cursor_type="row", zebra_stripes=True)
                yield Static(tr("tui.automation_inventory.requests"))
                yield DataTable(id="automation-inventory-requests", cursor_type="row", zebra_stripes=True)
                yield Static("", id="automation-inventory-details", markup=False)
            yield Static("", id="automation-inventory-status", markup=False)
            yield Button(tr("tui.automation_inventory.refresh"), id="automation-inventory-refresh")
            yield Button(tr("tui.automation_inventory.approve"), id="automation-inventory-approve", disabled=True)
            yield Button(tr("tui.automation_inventory.decline"), id="automation-inventory-decline", disabled=True)
            yield Button(tr("tui.automation_inventory.close"), id="automation-inventory-close")

    def on_mount(self) -> None:
        """Prepare native tables and explicitly read the first inventory."""
        for suffix in ("grants", "keys", "requests"):
            table = cast("DataTable[str]", self.query_one(f"#automation-inventory-{suffix}", DataTable))
            table.add_columns(
                tr("tui.automation_inventory.id"),
                tr("tui.automation_inventory.state"),
                tr("tui.automation_inventory.expires"),
            )
        self._lifetime_timer = self.set_interval(0.5, self._check_bound_lifetime)
        self.call_after_refresh(self._start_refresh)

    async def on_unmount(self) -> None:
        """Clear rows and retain the native read until its worker settles."""
        self._live = False
        if self._lifetime_timer is not None:
            self._lifetime_timer.stop()
            self._lifetime_timer = None
        self._clear()
        worker = self._worker
        if worker is not None:
            worker.cancel()
            with suppress(WorkerCancelled, WorkerError, WorkerFailed, asyncio.CancelledError):
                await await_cancellation_complete(worker.wait(), task_name="tui-automation-inventory-drain")

    def _clear(self) -> None:
        self._inventory = None
        self._selected_review = None
        for table in self.query("DataTable"):
            cast("DataTable[str]", table).clear()
        for details in self.query(Static):
            if details.id == "automation-inventory-details":
                details.update("")
        if self.is_mounted:
            self._decision_controls()

    def _decision_controls(self) -> None:
        enabled = self._selected_review is not None and not self._busy and not self._access_lost and self._live
        for decision in ("approve", "decline"):
            for button in self.query(f"#automation-inventory-{decision}"):
                cast("Button", button).disabled = not enabled

    def _bound_identity(self) -> bool:
        try:
            return (
                self._client.frontend is OperationFrontendProjection.TUI
                and self._client.profile_id == self._profile_id
                and self._client.session_id == self._session_id
            )
        except Exception:
            return False

    def _check_bound_lifetime(self) -> None:
        """Clear cached facts at the known deadline without touching authority."""
        if not self._live or self._access_lost:
            return
        expires_at = self._known_session_expires_at
        if not self._bound_identity() or (expires_at is not None and expires_at <= datetime.now(UTC)):
            self._lose_access()

    async def _bound_status(self) -> bool:
        if not self._bound_identity():
            return False
        try:
            reply = await await_cancellation_complete(
                asyncio.to_thread(self._client.status), task_name="tui-automation-inventory-status"
            )
        except Exception:
            return False
        status = reply.status
        valid = (
            self._bound_identity()
            and status.connected
            and status.credential_authenticated
            and status.profile_bound
            and status.profile_id == self._profile_id
            and status.session_id == self._session_id
            and status.session_expires_at is not None
            and status.session_expires_at > datetime.now(UTC)
            and status.denial is None
        )
        if valid:
            self._known_session_expires_at = status.session_expires_at
        return valid

    def _lose_access(self) -> None:
        self._access_lost = True
        self._clear()
        if self._live and self.is_mounted:
            self.query_one("#automation-inventory-status", Static).update(tr("tui.automation_inventory.access_lost"))
            self.query_one("#automation-inventory-refresh", Button).disabled = True
            self._decision_controls()

    def _show(self, inventory: AutomationInventoryProjection) -> None:
        if not self._live or not self.is_mounted or self._access_lost:
            return
        self._inventory = inventory
        for suffix, rows in (
            ("grants", inventory.grants),
            ("keys", inventory.keys),
            ("requests", inventory.requests),
        ):
            table = cast("DataTable[str]", self.query_one(f"#automation-inventory-{suffix}", DataTable))
            table.clear()
            for item in rows:
                if isinstance(item, AutomationGrantProjection):
                    row = (str(item.grant_id), item.state.value, item.expires_at.isoformat())
                elif isinstance(item, AutomationKeyProjection):
                    row = (str(item.key_id), item.state.value, item.expires_at.isoformat())
                else:
                    row = (str(item.receipt.request_id), item.receipt.stage.value, item.expires_at.isoformat())
                table.add_row(*row)
        self.query_one("#automation-inventory-details", Static).update(
            _grant_detail(inventory.grants[0])
            if inventory.grants
            else _request_detail(inventory.requests[0])
            if inventory.requests
            else _key_detail(inventory.keys[0])
            if inventory.keys
            else tr("tui.automation_inventory.empty")
        )
        self.query_one("#automation-inventory-status", Static).update("")
        self._decision_controls()

    def _start_refresh(self) -> None:
        if self._busy or self._access_lost or not self._live or not self.is_mounted:
            return
        self._worker = self.run_worker(self._refresh(), group="automation-inventory", exclusive=True)

    async def _refresh(self) -> None:
        self._busy = True
        self.query_one("#automation-inventory-refresh", Button).disabled = True
        self._decision_controls()
        self._clear()
        try:
            if not await self._bound_status():
                self._lose_access()
                return
            completed = await await_cancellation_complete(
                asyncio.to_thread(read_automation_inventory, self._client), task_name="tui-automation-inventory-read"
            )
            if not await self._bound_status():
                self._lose_access()
                return
            if self._live:
                self._show(completed.projection)
        except Exception:
            self._clear()
            if not await self._bound_status():
                self._lose_access()
            elif self._live and self.is_mounted:
                self.query_one("#automation-inventory-status", Static).update(
                    tr("tui.automation_inventory.unavailable")
                )
        finally:
            self._busy = False
            if self._live and self.is_mounted and not self._access_lost:
                self.query_one("#automation-inventory-refresh", Button).disabled = False
                self._decision_controls()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Show the selected row's public details without another runtime read."""
        inventory = self._inventory
        if inventory is None or not self._live or self._access_lost:
            return
        index = event.cursor_row
        table = cast("DataTable[str]", event.data_table)
        if table.id == "automation-inventory-grants" and index < len(inventory.grants):
            self._selected_review = None
            details = _grant_detail(inventory.grants[index])
        elif table.id == "automation-inventory-keys" and index < len(inventory.keys):
            self._selected_review = None
            details = _key_detail(inventory.keys[index])
        elif table.id == "automation-inventory-requests" and index < len(inventory.requests):
            self._selected_review = inventory.requests[index]
            details = _request_detail(self._selected_review)
        else:
            return
        self.query_one("#automation-inventory-details", Static).update(details)
        self._decision_controls()

    def _on_decision_closed(
        self, screen: RuntimeAutomationDecisionScreen, outcome: AutomationDecisionUiOutcome | None
    ) -> None:
        if not self._live or not self.is_mounted:
            return
        if screen.access_lost or (outcome is not None and outcome.access_lost):
            self._lose_access()
            return
        if outcome is None:
            return
        if outcome.operation_id is not None:
            self._clear()
        label = tr("tui.automation_decision.completed" if outcome.completed else "tui.automation_decision.unavailable")
        parts = [label]
        if outcome.operation_id is not None:
            parts.append(f"{tr('tui.automation_decision.operation_id')}: {outcome.operation_id}")
            if outcome.terminal_condition is not None:
                parts.append(f"{tr('tui.automation_decision.terminal_condition')}: {outcome.terminal_condition.value}")
            effect = (
                outcome.effect.value if outcome.effect is not None else tr("tui.automation_decision.unknown_effect")
            )
            parts.append(f"{tr('tui.automation_decision.effect')}: {effect}")
        self.query_one("#automation-inventory-status", Static).update(" · ".join(parts))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle an explicit refresh or close action."""
        if event.button.id == "automation-inventory-close":
            self.action_close()
        elif event.button.id == "automation-inventory-refresh":
            self._start_refresh()
        elif event.button.id in {"automation-inventory-approve", "automation-inventory-decline"}:
            review = self._selected_review
            inventory = self._inventory
            if self._busy or self._access_lost:
                return
            if review is None or inventory is None:
                self.query_one("#automation-inventory-status", Static).update(
                    tr("tui.automation_decision.missing_selection")
                )
                return
            if not self._bound_identity():
                self._lose_access()
                return
            if not any(item is review for item in inventory.requests):
                self._selected_review = None
                self._decision_controls()
                return
            decision = "approve" if event.button.id == "automation-inventory-approve" else "decline"
            modal = RuntimeAutomationDecisionScreen(
                self._client,
                review,
                decision=decision,
                consent_text=_request_detail(review),
                session_expires_at=self._known_session_expires_at,
                on_access_lost=self._lose_access,
            )
            cast("App[object]", self.app).push_screen(modal, lambda outcome: self._on_decision_closed(modal, outcome))

    def action_close(self) -> None:
        """Close this view without closing its borrowed runtime client."""
        self.dismiss(self._access_lost)


__all__ = ["RuntimeAutomationInventoryScreen"]
