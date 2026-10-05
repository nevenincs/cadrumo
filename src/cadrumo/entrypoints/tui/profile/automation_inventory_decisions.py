"""Decision-modal lifecycle for automation inventory review rows."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import App
from textual.widgets import Button, Static

from ....core.i18n.render import tr
from ..secret.automation_decision import RuntimeAutomationDecisionScreen
from ..secret.automation_decision_outcome import AutomationDecisionUiOutcome
from .automation_inventory_details import _request_detail

if TYPE_CHECKING:
    from .automation_inventory import RuntimeAutomationInventoryScreen


def _decision_status(outcome: AutomationDecisionUiOutcome) -> str:
    label = tr("tui.automation_decision.completed" if outcome.completed else "tui.automation_decision.unavailable")
    parts = [label]
    if outcome.operation_id is not None:
        parts.append(f"{tr('tui.automation_decision.operation_id')}: {outcome.operation_id}")
        if outcome.terminal_condition is not None:
            parts.append(f"{tr('tui.automation_decision.terminal_condition')}: {outcome.terminal_condition.value}")
        effect = outcome.effect.value if outcome.effect is not None else tr("tui.automation_decision.unknown_effect")
        parts.append(f"{tr('tui.automation_decision.effect')}: {effect}")
    return " · ".join(parts)


class AutomationInventoryDecisionMixin:
    """Open review decisions only for a selected, still-bound inventory request."""

    def _on_decision_closed(
        self: RuntimeAutomationInventoryScreen,
        screen: RuntimeAutomationDecisionScreen,
        outcome: AutomationDecisionUiOutcome | None,
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
        self.query_one("#automation-inventory-status", Static).update(_decision_status(outcome))

    def on_button_pressed(
        self: RuntimeAutomationInventoryScreen,
        event: Button.Pressed,
    ) -> None:
        """Handle an explicit refresh, review decision, or close action."""
        button_id = event.button.id
        if button_id == "automation-inventory-close":
            self.action_close()
        elif button_id == "automation-inventory-refresh":
            self._start_refresh()
        elif button_id in {"automation-inventory-approve", "automation-inventory-decline"}:
            self._start_decision(button_id)

    def _start_decision(self: RuntimeAutomationInventoryScreen, button_id: str | None) -> None:
        if self._busy or self._access_lost:
            return
        review = self._selected_review
        inventory = self._inventory
        if review is None or inventory is None:
            self.query_one("#automation-inventory-status", Static).update(
                tr("tui.automation_decision.missing_selection")
            )
            return
        if not self._binding.identity_holds():
            self._lose_access()
            return
        if not any(item is review for item in inventory.requests):
            self._selected_review = None
            self._decision_controls()
            return
        decision = "approve" if button_id == "automation-inventory-approve" else "decline"
        modal = RuntimeAutomationDecisionScreen(
            self._client,
            review,
            decision=decision,
            consent_text=_request_detail(review),
            session_expires_at=self._binding.known_expires_at,
            on_access_lost=self._lose_access,
        )
        cast("App[object]", self.app).push_screen(modal, lambda outcome: self._on_decision_closed(modal, outcome))

    def action_close(self: RuntimeAutomationInventoryScreen) -> None:
        """Close this view without closing its borrowed runtime client."""
        self.dismiss(self._access_lost)
