"""Read-only rendering and selection behavior for automation inventory."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.widgets import DataTable, Static

from ....application.user_profile.automation_enrollment import (
    AutomationGrantProjection,
    AutomationInventoryProjection,
    AutomationKeyProjection,
    AutomationReviewProjection,
)
from ....core.i18n.render import tr
from .automation_inventory_details import _grant_detail, _key_detail, _request_detail

if TYPE_CHECKING:
    from .automation_inventory import RuntimeAutomationInventoryScreen


def _table_row(item: object) -> tuple[str, str, str]:
    if isinstance(item, AutomationGrantProjection):
        return str(item.grant_id), item.state.value, item.expires_at.isoformat()
    if isinstance(item, AutomationKeyProjection):
        return str(item.key_id), item.state.value, item.expires_at.isoformat()
    if isinstance(item, AutomationReviewProjection):
        return str(item.receipt.request_id), item.receipt.stage.value, item.expires_at.isoformat()
    raise TypeError("automation inventory contains an unknown projection")


def _first_detail(inventory: AutomationInventoryProjection) -> str:
    if inventory.grants:
        return _grant_detail(inventory.grants[0])
    if inventory.requests:
        return _request_detail(inventory.requests[0])
    if inventory.keys:
        return _key_detail(inventory.keys[0])
    return tr("tui.automation_inventory.empty")


class AutomationInventoryViewMixin:
    """Render inventory projections and keep row selection display-only."""

    def _clear(self: RuntimeAutomationInventoryScreen) -> None:
        self._inventory = None
        self._selected_review = None
        for table in self.query("DataTable"):
            cast("DataTable[str]", table).clear()
        for details in self.query(Static):
            if details.id == "automation-inventory-details":
                details.update("")
        if self.is_mounted:
            self._decision_controls()

    def _decision_controls(self: RuntimeAutomationInventoryScreen) -> None:
        enabled = self._selected_review is not None and not self._busy and not self._access_lost and self._live
        for decision in ("approve", "decline"):
            for button in self.query(f"#automation-inventory-{decision}"):
                button.disabled = not enabled

    def _show(self: RuntimeAutomationInventoryScreen, inventory: AutomationInventoryProjection) -> None:
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
                table.add_row(*_table_row(item))
        self.query_one("#automation-inventory-details", Static).update(_first_detail(inventory))
        self.query_one("#automation-inventory-status", Static).update("")
        self._decision_controls()

    def on_data_table_row_highlighted(
        self: RuntimeAutomationInventoryScreen,
        event: DataTable.RowHighlighted,
    ) -> None:
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
