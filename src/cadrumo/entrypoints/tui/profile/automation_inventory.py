"""Human automation inventory presented from one bound runtime session."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import ClassVar, cast, override

from textual.app import ComposeResult
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
    AutomationInventoryProjection,
    AutomationReviewProjection,
)
from ....core.async_cleanup import await_cancellation_complete
from ....core.i18n.render import tr
from ..bound_session import BoundSession
from ..components.theme import tokenised
from .automation_inventory_decisions import AutomationInventoryDecisionMixin
from .automation_inventory_view import AutomationInventoryViewMixin

_STATUS_TASK_NAME = "tui-automation-inventory-status"


async def _read_inventory(
    binding: BoundSession,
    client: RuntimeFrontendClient,
) -> AutomationInventoryProjection | None:
    if not await binding.confirm_with_runtime(task_name=_STATUS_TASK_NAME):
        return None
    completed = await await_cancellation_complete(
        asyncio.to_thread(read_automation_inventory, client), task_name="tui-automation-inventory-read"
    )
    if not await binding.confirm_with_runtime(task_name=_STATUS_TASK_NAME):
        return None
    return completed.projection


class RuntimeAutomationInventoryScreen(
    AutomationInventoryDecisionMixin,
    AutomationInventoryViewMixin,
    ModalScreen[bool | None],
):
    """Borrow one TUI session; the runtime remains the sole inventory authority."""

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]
    DEFAULT_CSS = tokenised("""
    RuntimeAutomationInventoryScreen { align: center middle; }
    #automation-inventory-body {
        width: $cadrumo-modal-width;
        height: $cadrumo-modal-height;
        border: $cadrumo-radius-overlay $accent;
        padding: $cadrumo-gutter-y $cadrumo-gutter;
        background: $surface;
    }
    #automation-inventory-content { height: 1fr; }
    #automation-inventory-grants, #automation-inventory-keys, #automation-inventory-requests {
        height: auto;
        max-height: $cadrumo-log-max-height;
    }
    #automation-inventory-details { height: 1fr; }
    """)

    def __init__(self, client: RuntimeFrontendClient) -> None:
        """Pin one admitted TUI connection without assuming inventory privilege."""
        super().__init__()
        if client.frontend is not OperationFrontendProjection.TUI:
            raise ValueError("automation inventory requires a TUI frontend")
        self._client = client
        self._binding = BoundSession(client)
        self._inventory: AutomationInventoryProjection | None = None
        self._selected_review: AutomationReviewProjection | None = None
        self._worker: Worker[None] | None = None
        self._busy = False
        self._live = True
        self._access_lost = False
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

    def _check_bound_lifetime(self) -> None:
        """Clear cached facts at the known deadline without touching authority."""
        if self._live and not self._access_lost and self._binding.lifetime_ended():
            self._lose_access()

    def _lose_access(self) -> None:
        self._access_lost = True
        self._clear()
        if self._live and self.is_mounted:
            self.query_one("#automation-inventory-status", Static).update(tr("tui.automation_inventory.access_lost"))
            self.query_one("#automation-inventory-refresh", Button).disabled = True
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
            inventory = await _read_inventory(self._binding, self._client)
            if inventory is None:
                self._lose_access()
                return
            if self._live:
                self._show(inventory)
        except Exception:
            self._clear()
            if not await self._binding.confirm_with_runtime(task_name=_STATUS_TASK_NAME):
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


__all__ = ["RuntimeAutomationInventoryScreen"]
