"""Widgets and public wording for the automation decision screen."""

from __future__ import annotations

from dataclasses import replace

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Button, Input, Static

from ....adapters.local_runtime.automation_decision import AutomationDecision
from ....core.i18n.render import tr
from .automation_decision_outcome import AutomationDecisionUiOutcome


def decision_widgets(decision: AutomationDecision, consent_text: str) -> ComposeResult:
    """Compose the exact consent and decision controls shown for this review."""
    with Vertical(id="automation-decision-body"):
        yield Static(tr("tui.automation_decision.title"))
        yield Static(tr("tui.automation_decision.consent"))
        with VerticalScroll(id="automation-decision-consent"):
            yield Static(consent_text, id="automation-decision-review", markup=False)
        if decision == "approve":
            yield Static(tr("tui.automation_decision.password"))
            yield Input(password=True, id="automation-decision-password")
        yield Static("", id="automation-decision-status", markup=False)
        yield Button(
            tr(
                "tui.automation_decision.confirm_approve"
                if decision == "approve"
                else "tui.automation_decision.confirm_decline"
            ),
            id="automation-decision-confirm",
        )
        yield Button(tr("tui.automation_decision.cancel"), id="automation-decision-cancel")


def decision_status_text(outcome: AutomationDecisionUiOutcome) -> str:
    """Render only the safe settlement facts retained by the modal."""
    parts = [tr("tui.automation_decision.completed" if outcome.completed else "tui.automation_decision.unavailable")]
    if outcome.operation_id is not None:
        parts.append(f"{tr('tui.automation_decision.operation_id')}: {outcome.operation_id}")
    if outcome.terminal_condition is not None:
        parts.append(f"{tr('tui.automation_decision.terminal_condition')}: {outcome.terminal_condition.value}")
    if outcome.effect is not None:
        parts.append(f"{tr('tui.automation_decision.effect')}: {outcome.effect.value}")
    elif outcome.operation_id is not None:
        parts.append(f"{tr('tui.automation_decision.effect')}: {tr('tui.automation_decision.unknown_effect')}")
    return " · ".join(parts)


def decision_close_outcome(
    outcome: AutomationDecisionUiOutcome | None,
    *,
    access_lost: bool,
) -> AutomationDecisionUiOutcome | None:
    """Mark a retained modal result when access ended before it was dismissed."""
    if not access_lost:
        return outcome
    if outcome is None:
        return AutomationDecisionUiOutcome(None, None, None, None, False, True)
    return replace(outcome, access_lost=True)


__all__ = ["decision_close_outcome", "decision_status_text", "decision_widgets"]
